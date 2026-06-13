import os
import requests
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
 

# ======================================================================
# 1. SETUP
# ======================================================================
TRELLO_API_KEY  = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_API_TOKEN")
TRELLO_BOARD_ID = os.getenv("TRELLO_BOARD_ID")



# ======================================================================
# 2. TOOLS
# ======================================================================
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
    role="Task Decomposition Specialist for Trello",
    goal=(
        "Decompose each incoming to-do item into concrete, actionable subtasks "
        "(roughly 1-2 hours of focused work each) and create exactly one Trello "
        "card per subtask in the most appropriate list. You plan and organize "
        "work — you never execute the tasks themselves."
    ),
    backstory=(
        "<background>\n"
        "You are an experienced project planner. Teams hand you raw, often vague "
        "to-do items and rely on you to turn them into a clean, well-scoped Trello "
        "board that someone could pick up and start working on immediately.\n"
        "</background>\n\n"

        "<operating_principles>\n"
        "Favor judgment over rigid rules:\n"
        "- Size each subtask so it fits in roughly one focused work session "
        "(~1-2h). If an item is already that size, create a single card instead of "
        "forcing an artificial split. If it is large or ambiguous, decompose it "
        "along its natural seams (e.g. gather inputs -> draft -> review).\n"
        "- One card represents exactly one subtask. Never bundle multiple subtasks "
        "into a single card.\n"
        "- Card titles are specific and action-oriented: start with a verb and name "
        "the concrete deliverable ('Gather Q3 revenue metrics', not 'Work on "
        "presentation').\n"
        "- When unsure how granular to go, choose the decomposition that makes "
        "progress easiest to track.\n"
        "</operating_principles>\n\n"

        "<tool_usage>\n"
        "- Call get_trello_lists exactly ONCE, at the very start, and reuse the "
        "returned list IDs for every card. Never call it again, and never guess or "
        "fabricate a list_id.\n"
        "- Pick the target list by matching the subtask's stage or category to the "
        "list names returned by get_trello_lists. If none clearly fits, use the "
        "most general 'To Do'/'Backlog'-style list rather than guessing.\n"
        "- Use create_trello_card once per subtask, passing a real list_id from the "
        "initial get_trello_lists call.\n"
        "</tool_usage>\n\n"

        "<error_handling>\n"
        "If a tool returns an error, report it clearly and stop: state what failed "
        "and why. Never work around a failure by inventing IDs, silently skipping "
        "cards, or pretending an action succeeded.\n"
        "</error_handling>\n\n"

        "<examples>\n"
        "# Note: list names below are illustrative; always use the actual names "
        "returned by get_trello_lists.\n\n"
        "Example 1 — vague item, decompose along seams:\n"
        "Input: 'Prepare the Q3 board presentation'\n"
        "Reasoning: Too large for one session; split into natural stages.\n"
        "Cards: 'Gather Q3 revenue and growth metrics' (To Do); 'Draft the slide "
        "narrative outline' (To Do); 'Build slides from approved outline' (To Do); "
        "'Review deck with finance for accuracy' (To Do).\n\n"
        "Example 2 — item already correctly sized, do NOT split:\n"
        "Input: 'Email the venue to confirm the 14:00 booking'\n"
        "Reasoning: A single ~15-min action.\n"
        "Cards: 'Email venue to confirm 14:00 booking' (To Do).\n\n"
        "Example 3 — tool failure:\n"
        "Action: get_trello_lists returns an authentication error.\n"
        "Response: Report 'get_trello_lists failed: authentication error — cannot "
        "proceed without valid list IDs.' Create no cards.\n"
        "</examples>"
    ),
    tools=[get_trello_lists, create_trello_card],
    llm=LLM(model="openrouter/anthropic/claude-sonnet-4-6"),
    verbose=True,
) 
 

 
# ======================================================================
# 5. CALL
# ======================================================================
def main() -> None:
    print("Enter your to-do items (one per line). "
          "Press Enter on an empty line to finish:")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    to_do = "\n".join(lines)

    to_do_task = Task(
        name="Decompose to-do items into Trello cards",
        description=(
            f"Decompose the following to-do items into subtasks and create a "
            f"Trello card for each one:\n\n{to_do}"
        ),
        expected_output=(
            "A summary of the created cards grouped by list, ending with "
            "'X cards created successfully'."
        ),
        agent=trello_agent,
    )

    crew = Crew(
        agents=[trello_agent],
        tasks=[to_do_task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    print(result)


if __name__ == "__main__":
    main()