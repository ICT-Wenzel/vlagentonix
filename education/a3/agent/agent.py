import os
import requests
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from crewai_tools import DirectoryReadTool, FileReadTool

 

# ======================================================================
# 1. SETUP
# ======================================================================
TRELLO_API_KEY  = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_API_TOKEN")
TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID")

directory_limit = "./files"
# ======================================================================
# 2. TOOLS
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
    return DirectoryReadTool(directory_limit + path)

@tool("read_file")
def read_file(path: str) -> str:
    """Read the full text content of a specific file.

    Use this tool to inspect the code, configuration, or text inside a file. Only call this after you have verified the file's exact name and path (ideally via `read_directory`). Do not guess file names or extensions. Avoid calling this on binary files like images or PDFs.

    Args:
        path: Relative path to the target file from the workspace root, e.g., "src/index.js" or "README.md". Must include the exact file extension. Always use forward slashes ('/') as separators.

    Returns:
        The complete textual content of the file, or an error message if the file does not exist, is too large, or cannot be parsed as text.
    """
    return FileReadTool(directory_limit + path)

@tool("get_trello_lists")
def get_trello_lists() -> str:
    """Return all lists on the Trello board with their names and IDs.
 
    Call this before create_trello_card to discover the available lists
    and their IDs. The ID returned here is exactly what must be passed
    as the list_id argument to create_trello_card. You cannot create a
    card without first retrieving a valid list ID from this tool.
 
    Returns:
        Each list as "name (ID: list_id)", comma-separated, e.g.
        "To Do (ID: 5abc123), Done (ID: 7ghi789)". Or an error message
        if the board cannot be accessed.
    """
    url = f"https://api.trello.com/1/boards/{TRELLO_BOARD_ID}/lists"
    params = {"key": TRELLO_API_KEY, "token": TRELLO_TOKEN}
 
    response = requests.get(url, params=params)
    response.raise_for_status()
 
    lists = response.json()
    eintraege = [f"{entry['name']} (ID: {entry['id']})" for entry in lists]
    return "Available lists: " + ", ".join(eintraege)
 
 
@tool("create_trello_card")
def create_trello_card(name: str, description: str, list_id: str) -> str:
    """Create a single Trello card in the specified list.
 
    For each individual subtask, call this tool exactly once - do not
    batch multiple tasks into one call. To create several cards,
    call this tool multiple times.
 
    Args:
        name: Short, actionable card title, e.g. "Design login page mockup".
            Keep it concise; put any detail into the description.
        description: Fuller explanation of the task, including context or
            acceptance criteria. May be empty if the title is self-explanatory.
        list_id: The ID of the target list. Call get_trello_lists first to
            retrieve both the list names and their IDs, then use the correct
            ID for this parameter. Do not guess or construct IDs.
 
    Returns:
        A confirmation with the card's title and ID, or an error message
        if the list ID is invalid or the board is inaccessible.
    """
    cards_url = "https://api.trello.com/1/cards"
    data = {
        "name": name,
        "desc": description,
        "idList": list_id,
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
    }
 
    response = requests.post(cards_url, params=data)
    response.raise_for_status()
    card = response.json()
    return f"Card '{card['name']}' was created in list '{list_id}'."
 
 

# ======================================================================
# 3. AGENT
# ======================================================================
trello_agent = Agent(
    role="File-Based Task Decomposition Specialist for Trello",
    goal=(
        "Scan a designated to-do directory for Markdown (.md) files, extract "
        "the raw to-do items from them, decompose each item into concrete, "
        "actionable subtasks (roughly 1-2 hours of focused work each), and create "
        "exactly one Trello card per subtask in the most appropriate list. You "
        "plan and organize work — you never execute the tasks themselves."
    ),
    backstory=(
        "<background>\n"
        "You are an experienced project planner who specializes in turning static "
        "text files into dynamic project boards. Teams leave their raw notes, "
        "brain dumps, and markdown checklists in a specific folder. Your job is to "
        "systematically ingest these files, find the tasks inside, and build a "
        "clean, well-scoped Trello board from them.\n"
        "</background>\n\n"

        "<operating_principles>\n"
        "Favor judgment over rigid rules:\n"
        "- Systematically process ALL Markdown files found in the target directory. "
        "Do not skip files unless they are empty or completely unrelated to tasks.\n"
        "- Size each subtask so it fits in roughly one focused work session "
        "(~1-2h). If an item in a file is already that size, create a single card "
        "instead of forcing an artificial split. If it is large or ambiguous, "
        "decompose it along its natural seams (e.g. gather inputs -> draft -> review).\n"
        "- One card represents exactly one subtask. Never bundle multiple subtasks "
        "into a single card.\n"
        "- Card titles are specific and action-oriented: start with a verb and name "
        "the concrete deliverable ('Gather Q3 revenue metrics', not 'Work on "
        "presentation').\n"
        "- When unsure how granular to go, choose the decomposition that makes "
        "progress easiest to track.\n"
        "</operating_principles>\n\n"

        "<tool_usage>\n"
        "- Step 1: Call get_trello_lists exactly ONCE at the very beginning to gather "
        "valid list IDs. Never guess or fabricate a list_id.\n"
        "- Step 2: Call read_directory to check the contents of the target folder. "
        "Identify all files ending with '.md'.\n"
        "- Step 3: For each Markdown file found, call read_file to extract its raw text content. "
        "Do not guess file content; read it entirely.\n"
        "- Step 4: Process the extracted text, decompose the tasks, and use create_trello_card "
        "for each resulting subtask, passing a real list_id from Step 1.\n"
        "- Pick the target list by matching the subtask's stage or category to the "
        "list names returned by get_trello_lists. If none clearly fits, use the "
        "most general 'To Do'/'Backlog'-style list.\n"
        "</tool_usage>\n\n"

        "<error_handling>\n"
        "If a tool returns an error (e.g., directory not found or file unreadable), "
        "report it clearly and stop: state what failed and why. Never work around a "
        "failure by inventing IDs, silently skipping files, or pretending an action succeeded.\n"
        "</error_handling>\n\n"

        "<examples>\n"
        "# Note: list names below are illustrative; always use the actual names "
        "returned by get_trello_lists.\n\n"
        "Example 1 — Complete workflow from directory to cards:\n"
        "1. get_trello_lists called -> Returns list 'To Do' (ID: 123).\n"
        "2. read_directory called for '.' -> Returns ['backlog.md', 'script.py'].\n"
        "3. read_file called for 'backlog.md' -> Content is: '- Prepare Q3 presentation'\n"
        "4. Decomposition: 'Prepare Q3 presentation' is too large.\n"
        "5. Cards created: 'Gather Q3 metrics' (ID 123), 'Draft slide outline' (ID 123).\n\n"
        "Example 2 — Empty directory or no markdown files:\n"
        "Action: read_directory returns only binary files or is empty.\n"
        "Response: Report 'No Markdown (.md) files found in the directory to process.' "
        "Create no cards.\n"
        "</examples>"
    ),
    tools=[get_trello_lists, create_trello_card, read_directory, read_file],
    llm=LLM(model="openrouter/anthropic/claude-sonnet-4-6"),
    verbose=True,
)
 

 
# ======================================================================
# 5. CALL
# ======================================================================
def main() -> None:
    inputs = {
        "target_directory": "/todo_folder"
    }

    to_do_task = Task(
        name="Scan directory and decompose Markdown to-dos into Trello cards",
        description=(
            "Scan the directory '{target_directory}' for all Markdown (.md) files. "
            "Read the text content of each file, extract the raw to-do items, "
            "decompose them into concrete subtasks (1-2 hours each), and create "
            "a Trello card for each subtask in the correct list."
        ),
        expected_output=(
            "A summary of the processed Markdown files, the tasks found inside them, "
            "and a list of the created Trello cards, ending with 'X cards created successfully'."
        ),
        agent=trello_agent,
    )

    crew = Crew(
        agents=[trello_agent],
        tasks=[to_do_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff(inputs=inputs)
    print(result)

if __name__ == "__main__":
    main()