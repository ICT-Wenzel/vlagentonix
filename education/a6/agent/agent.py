# ======================================================================
# 1. SETUP
# ======================================================================
import os
import sys
import requests
from pydantic import BaseModel, Field
from typing import List
from crewai import Agent, Task, Crew, Process, LLM, Memory
from crewai.tools import tool
from crewai_tools import DirectoryReadTool, FileReadTool
from sandbox import run_code


TRELLO_API_KEY  = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_API_TOKEN")
TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

directory_limit = "./files"
 
EMBED_MODEL = "text-embedding-3-large"
MEMORY_DIR  = os.getenv("MEMORY_DIR", "./memory")



# ======================================================================
# 2. Output
# ======================================================================
class ExecutionAttempt(BaseModel):
    code: str = Field(description="The Python code that was executed in this attempt")
    exit_code: int = Field(description="The exit code returned by the sandbox")
    stdout: str = Field(description="Standard output captured from the run")
    stderr: str = Field(description="Standard error captured from the run")
    timed_out: bool = Field(description="Whether the run was killed for exceeding the time limit")
    succeeded: bool = Field(description="Whether this attempt ran cleanly (exit code 0, no error)")
 
class CodeExecutionResult(BaseModel):
    task: str = Field(description="The original task the agent was asked to solve")
    final_code: str = Field(description="The final, working Python code that solved the task")
    final_output: str = Field(description="The stdout the final code produced in the sandbox")
    success: bool = Field(description="Whether the task was solved successfully")
    attempts: List[ExecutionAttempt] = Field(description="Every execution attempt in order, including failed ones")
    total_attempts: int = Field(description="Total number of execution attempts made")
    summary: str = Field(description="Brief summary of how the task was solved")



# ======================================================================
# 3. TOOLS
# ======================================================================
@tool("read_directory")
def read_directory(path: str) -> str:
    """List all files and subdirectories contained within a specific directory.

    Use this tool to explore the project structure or locate files before attempting to read or modify them. Call this whenever you need to verify if a file exists. Do not guess file paths.
    To inspect the actual content of a specific file found here, use the `read_file` tool.

    Args:
        path: Relative path to the target directory from the workspace root, e.g., "src/components" or "." for the root directory. Always use forward slashes ('/') as separators. Do not use absolute system paths.

    Returns:
        A formatted list of files and subdirectories, or an error message if the path does not exist or access is denied.
    """
    base = os.path.realpath(directory_limit)
    full = os.path.realpath(os.path.join(base, path.replace("\\", "/").lstrip("/")))
    if not (full == base or full.startswith(base + os.sep)):
        return f"Error: Access denied — '{path}' is outside the workspace."
    if not os.path.exists(full):
        return f"Error: Directory '{path}' does not exist."
    if not os.path.isdir(full):
        return f"Error: '{path}' is a file, not a directory. Use read_file instead."
    try:
        entries = sorted(os.listdir(full))
    except PermissionError:
        return f"Error: Access denied to '{path}'."
    if not entries:
        return f"'{path}' is empty (no files or subdirectories)."
    return "\n".join(
        f"{'[DIR] ' if os.path.isdir(os.path.join(full, e)) else '[FILE]'} {e}"
        for e in entries
    )


@tool("read_file")
def read_file(path: str) -> str:
    """Read the full text content of a specific file.

    Use this tool to inspect the code, configuration, or text inside a file. Only call this after you have verified the file's exact name and path (ideally via `read_directory`). Do not guess file names or extensions. Avoid calling this on binary files like images or PDFs.

    Args:
        path: Relative path to the target file from the workspace root, e.g., "src/index.js" or "README.md". Must include the exact file extension. Always use forward slashes ('/') as separators.

    Returns:
        The complete textual content of the file, or an error message if the file does not exist, is too large, or cannot be parsed as text.
    """
    base = os.path.realpath(directory_limit)
    full = os.path.realpath(os.path.join(base, path.replace("\\", "/").lstrip("/")))
    if not (full == base or full.startswith(base + os.sep)):
        return f"Error: Access denied — '{path}' is outside the workspace."
    if not os.path.exists(full):
        return f"Error: File '{path}' does not exist."
    if os.path.isdir(full):
        return f"Error: '{path}' is a directory, not a file. Use read_directory instead."
    if os.path.getsize(full) > 1_000_000:
        return f"Error: File '{path}' is too large (limit 1000000 bytes)."
    try:
        with open(full, "rb") as fb:
            raw = fb.read()
        if b"\x00" in raw:
            return f"Error: '{path}' appears to be binary and cannot be parsed as text."
        return raw.decode("utf-8")
    except PermissionError:
        return f"Error: Access denied to '{path}'."
    except UnicodeDecodeError:
        return f"Error: '{path}' cannot be parsed as UTF-8 text (likely binary)."


@tool("execute_python")
def execute_python(code: str) -> str:
    """Execute a self-contained Python script inside an isolated, hardened sandbox.
 
    Use this tool to actually run code and verify its behavior. Never assume what a
    snippet will produce — always execute it here and base your conclusions on the real
    output. The script runs in a short-lived Docker container with no network access,
    limited CPU and memory, a read-only filesystem, and a hard timeout. Call this
    whenever you have written or revised code and need to confirm that it works. If the
    result shows a non-zero exit code or a traceback in stderr, read the error message,
    fix the code, and call this tool again. Do not guess at the cause of a failure
    without re-running the corrected code.
 
    Args:
        code: A complete, standalone Python script to execute. It must run on its own,
            without relying on external files, arguments, or installed third-party
            packages. Print anything you want to inspect to stdout — return values are
            not captured, only what the script prints. No network is available, so do
            not attempt HTTP requests, downloads, or package installation.
 
    Returns:
        A formatted report with the exit code, a timeout notice if the run was killed
        for exceeding the time limit, and the captured stdout and stderr. Returns an
        error message instead if the sandbox itself could not be started.
    """
    result = run_code(code)
 
    lines = [f"exit_code: {result['exit_code']}"]
    if result["timed_out"]:
        lines.append("NOTE: execution was killed because it exceeded the time limit.")
    lines.append("--- stdout ---")
    lines.append(result["stdout"] or "(empty)")
    lines.append("--- stderr ---")
    lines.append(result["stderr"] or "(empty)")
    return "\n".join(lines)



# ======================================================================
# 4. AGENT
# ======================================================================
code_agent = Agent(
    role="File-Driven Python Code Generation and Execution Specialist",
    goal=(
        "Scan a designated specification directory for the file(s) that describe what "
        "to build, read them in full, write a complete Python program that fulfils the "
        "specification, and execute that program in an isolated sandbox. Iterate on any "
        "failure — reading the real error output and correcting the code — until the "
        "program runs cleanly AND its output actually satisfies the specification. You "
        "write and verify code; you never assume what code does without running it. You "
        "may be run repeatedly on the same specification until it is solved, so you first "
        "recall what earlier runs already learned and build on it, rather than starting "
        "over each time."
    ),
    backstory=(
        "<background>\n"
        "You are an experienced Python developer who works strictly from written "
        "specifications. Teams drop a spec — a feature request, a function description, "
        "a small task — as a file into a designated folder. Your job is to read that "
        "spec, implement it in Python, and PROVE that it works by running it in an "
        "isolated, hardened sandbox. You never trust code you have only read; you trust "
        "code you have executed and seen succeed.\n"
        "</background>\n\n"
 
        "<operating_principles>\n"
        "Favor judgment over rigid rules:\n"
        "- Read the specification COMPLETELY before writing a single line of code. Do "
        "not start coding from the filename or a partial reading.\n"
        "- Write complete, self-contained scripts. The sandbox has NO network access "
        "and NO third-party packages — use only the Python standard library.\n"
        "- Print everything you need to observe to stdout. Return values are NOT "
        "captured; only what the script prints is visible to you.\n"
        "- Never declare a task done without a successful sandbox run. 'It should work' "
        "is not acceptable; 'it ran and produced this output' is.\n"
        "- Treat a failed run as information, not defeat: read stderr, identify the "
        "cause, fix the code, and run again.\n"
        "- Distinguish RAN from CORRECT. A clean exit code only means the code "
        "executed — verify the output genuinely matches what the specification asked "
        "for.\n"
        "- Keep your scripts focused on the spec. Do not add unrelated functionality.\n"
        "</operating_principles>\n\n"
 
        "<memory_usage>\n"
        "You have a PERSISTENT memory that survives across runs. This is critical, "
        "because a single specification may take several runs to solve, and you must "
        "never waste a fresh run repeating an approach that already failed.\n"
        "- BEFORE writing any code, recall from your memory everything recorded about "
        "THIS specification in previous runs: which approaches were already tried, which "
        "errors were already encountered (and their cause), the current best version of "
        "the code, and whether the task was already solved.\n"
        "- If memory shows the task was already solved, do not redo it — report the "
        "known solution and stop.\n"
        "- If memory shows earlier failed attempts, build on them: never repeat an "
        "approach that already failed for the same reason. Start from the last recorded "
        "state instead of from scratch.\n"
        "- At the END of your work, write a precise, structured note into memory for the "
        "next run: the specification you worked on, every approach and error you hit THIS "
        "run (with the cause), the current best code, whether it is solved, and — if not "
        "solved — exactly where you stopped and what to try next. This recap is what the "
        "next run reads first, so be precise and complete.\n"
        "</memory_usage>\n\n"
 
        "<stopping_and_continuation>\n"
        "You do NOT have to solve the task in a single run. Work to a fixed budget:\n"
        "- Make at most 5 execution attempts (calls to execute_python) per run.\n"
        "- If the program runs cleanly AND correctly within that budget, you are done: "
        "report success.\n"
        "- If you reach 5 attempts without success, STOP cleanly. Do not keep trying. "
        "Record the discovered errors and the current best code into memory (see "
        "<memory_usage>) and report the task as 'not solved yet — will continue next "
        "run', stating clearly what the next run should try first.\n"
        "- Stopping at the budget is the correct, expected behavior, not a failure. The "
        "next run picks up exactly where you left off and avoids the errors you already "
        "found.\n"
        "</stopping_and_continuation>\n\n"
 
        "<tool_usage>\n"
        "- Step 1: Call read_directory on the target directory exactly ONCE to discover "
        "the specification file(s). Never guess file paths.\n"
        "- Step 2: For each relevant specification file, call read_file to read its full "
        "content. Do not guess file content; read it entirely.\n"
        "- Step 3: Based on the specification, write a complete Python script.\n"
        "- Step 4: Call execute_python with that script to run it in the sandbox.\n"
        "- Step 5: Inspect the returned exit_code, stdout and stderr. If the run failed "
        "(non-zero exit code, a traceback in stderr, a timeout, or output that does not "
        "match the spec), correct the script and call execute_python again. Repeat until "
        "the run is clean AND correct, OR until you reach this run's attempt budget (see "
        "<stopping_and_continuation>) — then stop and record your progress to memory.\n"
        "- Each execute_python run starts in a FRESH container with no retained state. "
        "Always pass a complete script, never fragments that depend on a previous run.\n"
        "</tool_usage>\n\n"
 
        "<error_handling>\n"
        "Two different kinds of failure, handled differently:\n"
        "- TOOL / infrastructure failures (read_directory or read_file returns an "
        "'Error:', or execute_python reports a 'sandbox error'): report clearly what "
        "failed and why, and STOP. Never invent file content, fabricate output, or "
        "pretend an action succeeded.\n"
        "- CODE failures (your script raises an exception or returns the wrong result "
        "INSIDE the sandbox): this is expected and is part of the job. Do NOT stop — "
        "read the error, fix the code, and run again. Only give up after a reasonable "
        "number of attempts, and if so, report the last error honestly.\n"
        "- Never report output you did not actually receive from execute_python.\n"
        "</error_handling>\n\n"
 
        "<examples>\n"
        "Example 1 — Spec file to working program:\n"
        "1. read_directory called for the target directory -> Returns ['task.md', 'notes.txt'].\n"
        "2. read_file called for 'task.md' -> Content: 'Write a function is_prime(n) and "
        "print whether each number from 1 to 20 is prime.'\n"
        "3. A complete script implementing is_prime and printing the results for 1..20 "
        "is written.\n"
        "4. execute_python called -> exit_code 0, stdout lists the primes, stderr empty.\n"
        "5. Report the final code and its actual output; success = true.\n\n"
        "Example 2 — First run fails, then is fixed:\n"
        "1-2. Spec read as above.\n"
        "3. execute_python called -> exit_code 1, stderr: \"NameError: name 'rang' is "
        "not defined\".\n"
        "4. The typo is corrected ('rang' -> 'range') and execute_python is called again.\n"
        "5. Second run -> exit_code 0, correct output. Report BOTH attempts; success = true.\n\n"
        "Example 3 — No specification file found:\n"
        "Action: read_directory returns only unrelated or binary files, or is empty.\n"
        "Response: Report 'No specification file found in the target directory to "
        "implement.' Write and run no code.\n"
        "</examples>"
    ),
    tools=[read_directory, read_file, execute_python],
    llm=LLM(model="openai/gpt-4"),
    max_iter=15,
    verbose=True,
)


# ======================================================================
# 5. TASK
# ======================================================================
inputs = {
    "target_directory": "/specs"
}
build_task = Task(
    name="Implement and verify a Python program from a specification file",
    description=(
        "Scan the directory '{target_directory}' for the file(s) that describe what to "
        "build. FIRST, recall from your persistent memory what previous runs already "
        "discovered about this specification: approaches tried, errors found (with their "
        "cause), the current best code, and whether it was already solved. Read the full "
        "content of each specification file and determine exactly what program is "
        "required. Write a complete, self-contained Python program, then execute it in "
        "the sandbox using execute_python. If a run fails or its output does not match "
        "the specification, read the error, correct the code, and run again — building on "
        "what memory already recorded and never repeating a known failed approach. Make "
        "at most 5 execution attempts this run. If the program is correct within that "
        "budget, report success; if not, STOP, record the discovered errors and the "
        "current best code into memory, and state what the next run should try first. "
        "Never declare success without a successful sandbox run, and never report output "
        "you did not actually receive from the sandbox."
    ),
    expected_output=(
        "A structured report containing: (1) what was recalled from memory about previous "
        "runs (approaches and errors already known), (2) which specification file(s) were "
        "read, (3) the current best Python code, (4) the actual stdout it produced in the "
        "sandbox, (5) every execution attempt THIS run — including the failed ones with "
        "their error output — and (6) a brief summary, including what was newly written "
        "to memory for the next run. End with a line in the form 'Solved in X attempts' "
        "or 'Stopped after X attempts — recorded for next run; next try: <...>'."
    ),
    agent=code_agent,
    output_pydantic=CodeExecutionResult,
)


# ======================================================================
# 6. CREW
# ======================================================================
memory = Memory(embedder={
    "provider": "openai",
    "config": {
        "model_name": "text-embedding-3-large",
    },
})
crew = Crew(
    agents=[code_agent],
    tasks=[build_task],
    process=Process.sequential,
    memory=memory,
    verbose=True,
)



# ======================================================================
# 7. CALL
# ======================================================================
def main() -> None:
    if "--reset" in sys.argv:
        import shutil
        if os.path.isdir(MEMORY_DIR):
            shutil.rmtree(MEMORY_DIR)
            print(f"Memory folder '{MEMORY_DIR}' deleted.")
        else:
            print(f"No memory folder found at '{MEMORY_DIR}'.")
        return

    result = crew.kickoff(inputs=inputs)
    print(result)
    structured = result.pydantic

    print(f"success: {structured.success}")
    print(f"total_attempts: {structured.total_attempts}")
    print(f"\nfinal_code:\n{structured.final_code}")
    print(f"final_output:\n{structured.final_output}")

    for attempt in structured.attempts:
        print(f"  attempt exit_code={attempt.exit_code} succeeded={attempt.succeeded}")

    print(structured.model_dump_json(indent=2))
if __name__ == "__main__":
    main()