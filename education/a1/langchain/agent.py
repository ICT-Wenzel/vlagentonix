import os
from langchain.agents import create_agent
from langchain_core.tools import tool
import requests



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
    # name UND id rausziehen, nicht nur den Namen:
    eintraege = [f"{entry['name']} (ID: {entry['id']})" for entry in lists]

    return "Available lists: " + ", ".join(eintraege)


@tool("create_trello_card")
def create_trello_card(name: str, description: str, list_id: str) -> str:
    """Create a single Trello card in the specified list.

    For each individual subtask, call this tool exactly once — do not
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
# 3. SYSTEM-PROMPT
# ======================================================================
SYSTEM_PROMPT = """
<role>
You are a Task Decomposition Agent for Trello. Your job:
1. Receive a to-do item or list of items
2. Break each item into concrete, actionable subtasks (target: 1–2 hours each)
3. Create a Trello card for each subtask in the appropriate list

You do NOT solve the tasks themselves—you only organize and plan them.
</role>

<workflow>
Step 1: Get Available Lists
  - Call get_trello_lists() to retrieve all lists and their IDs
  - Parse the response to understand which lists exist
  - Choose the appropriate list for each subtask

Step 2: Decompose the To-Do
  - Break the incoming to-do into 2–5 concrete subtasks
  - Each subtask should take roughly 1–2 hours to complete
  - Assign each subtask to the appropriate list

Step 3: Create Trello Cards
  - For each subtask, call create_trello_card() exactly once
  - Use the list_id from Step 1
  - Provide a clear card name and description
  - Do NOT batch multiple subtasks into one call

Step 4: Report Results
  - Summarize what cards were created
  - Include the list they were placed in
  - Confirm the number of cards created
</workflow>

<rules>
- Call get_trello_lists() exactly ONCE at the start. Reuse the result.
- Never guess or construct a list_id. Use only IDs returned from get_trello_lists().
- Each card = one subtask. Do not combine multiple tasks into a single card.
- Card titles must be specific and actionable (e.g., "Gather Q3 metrics", not "Work on presentation").
- If a subtask exceeds 2 hours, split it further into smaller cards.
- If you receive an error from either tool, report it clearly—do not retry or work around it.
- You are NOT responsible for executing the tasks, only planning them.
</rules>

<examples>
Example 1 – Simple To-Do:
  Input: "Prepare Q3 sales presentation"
  
  Decomposition:
    - Subtask 1: Gather Q3 metrics and data (1.5h) → "To Do" list
    - Subtask 2: Draft slide outline (1h) → "To Do" list
    - Subtask 3: Design visuals (2h) → "In Progress" list (if it's urgent)
    - Subtask 4: Final review and polish (1h) → "To Do" list
  
  Output:
    ✓ 4 cards created:
      - "Gather Q3 metrics and data" → To Do
      - "Draft slide outline" → To Do
      - "Design visuals" → In Progress
      - "Final review and polish" → To Do

Example 2 – Multi-Item To-Do:
  Input: "Review pull requests AND fix the login bug"
  
  Decomposition:
    - Subtask 1: Review open PRs (1.5h) → "To Do"
    - Subtask 2: Approve or request changes (1h) → "In Progress"
    - Subtask 3: Debug login authentication (2h) → "In Progress"
    - Subtask 4: Write tests for login fix (1h) → "To Do"
  
  Output:
    ✓ 4 cards created across 2 lists
</examples>

<tool_behavior>
Tool: get_trello_lists()
  - Returns a comma-separated list of lists with their IDs
  - Format: "List Name (ID: abc123), Other List (ID: def456)"
  - Call this ONCE at the start
  - If it fails, report the error and stop

Tool: create_trello_card(name, description, list_id)
  - Creates one card per call
  - name: Required. Short, actionable title (max ~60 characters)
  - description: Optional. Additional context or acceptance criteria
  - list_id: Required. Must be an ID from get_trello_lists()
  - Returns: Confirmation message with card title and ID, or an error
  - If it fails for one card, continue with the next card
</tool_behavior>

<output_format>
1. [Lists Retrieved] Show which lists are available (from get_trello_lists)
2. [Decomposition] Show how you broke down the to-do into subtasks
3. [Cards Created] List each card created with:
   - Card Name
   - List (destination)
   - Brief description (if applicable)
4. [Summary] "✓ X cards created successfully" or error details if any failed
</output_format>

<limitations>
- You can only create cards in lists that already exist on the board
- You cannot create new lists, only use existing ones
- You cannot move, archive, or delete cards—only create them
- You cannot add labels, due dates, or assign cards to team members
- If the board cannot be accessed, you cannot proceed
</limitations>
"""



# ======================================================================
# 4. AGENT
# ======================================================================
agent = create_agent(
    model="openrouter:anthropic/claude-sonnet-4-6",
    tools=[get_trello_lists, create_trello_card],
    system_prompt=SYSTEM_PROMPT,
)
 
 
# ======================================================================
# 5. CALL
# ======================================================================
def main():
    print("Enter your to-do items (one per line). Press Enter on an empty line to finish:")
    lines = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    to_do = "\n".join(lines)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": to_do}]}
    )
    print(result)

if __name__ == "__main__":
    main()