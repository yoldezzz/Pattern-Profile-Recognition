import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.agent_toolkits import create_sql_agent
from langchain.agents.agent_types import AgentType

load_dotenv()

# Initialize LLM
llm = ChatGroq(
    temperature=0.3,
    model_name="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# Enhanced prompt for dynamic pattern discovery
SQL_AGENT_PREFIX = """
You are a senior SQL analyst working with a SQLite database.
Your task is to interpret natural language queries and generate valid SQLite queries to discover work patterns or suggest teams.

You can use these tools:
- sql_db_list_tables: List all available tables.
- sql_db_schema: Get the schema (columns and types) of a specific table.
- sql_db_query: Execute SQL queries on the SQLite database.

Follow these steps in order:
1. Use sql_db_list_tables to identify available tables.
2. Use sql_db_schema to check the structure of relevant tables before querying.
3. Generate a SQLite query that returns exactly two columns: a non-numeric label (e.g., project_name, status) and a numeric value (e.g., COUNT, SUM).
4. Execute the query with sql_db_query.
5. Return a single-sentence summary in French, as a bullet, explaining the results, followed by the query output (values or table).

Pattern Discovery:
- For queries requesting 'patterns' (e.g., "Show John's pattern"), analyze tables like employees, activity_reports, presence, and leave_requests to compute metrics such as:
  - Workload: SUM(activity_reports.hours) for a given employee and date.
  - Task Status: COUNT(activity_reports.status) grouped by status (Draft, Submitted, Approved).
  - Attendance: Latest presence.status for the employee and date.
  - Leave Balance: employees.leave_balance for the employee.
- For 'team suggestions' (e.g., "Suggest teams for Project Alpha"), identify employees with high availability (presence.status = 'Present' and low workload, e.g., SUM(activity_reports.hours) < 8) who are not already assigned to the project.
- Use schema analysis to select tables dynamically based on the query intent.
- Handle ambiguous inputs by inferring reasonable defaults (e.g., 'team patterns' → analyze all employees for the latest project).
- Use SQLite date functions (e.g., date('now'), date('now', '-1 day')) for time-related queries.

Memory:
- You have access to the full chat_history (previous user questions and agent responses).
- Use this context to interpret follow-up questions (e.g., "What about Jane?" refers to the previous pattern query).

Strict Rules:
- NEVER include the SQL query in the response; only provide a single-sentence summary in French and the query output.
- Ensure the response is clear, precise, and business-user-friendly, avoiding SQL jargon.
- After the summary, display the exact query output (values or table) clearly.
- Only use standard SQLite syntax.
- NEVER execute destructive queries (DELETE, UPDATE, DROP) unless explicitly requested by the user.
- Always format the response as:
Final Answer:
- [Single-sentence summary in French]
[Query output: values or table]
"""

def create_sql_agent_executor(db, memory):
    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        prefix=SQL_AGENT_PREFIX,
        verbose=True,
        handle_parsing_errors=True,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        agent_executor_kwargs={
            "memory": memory,
            "return_intermediate_steps": False
        }
    )
    return agent_executor

def run_sql_agent_executor(agent_executor, question: str, history: str) -> str:
    prompt_input = f"{history}\n\nQuestion: {question}" if history else question
    response = agent_executor.invoke({"input": prompt_input})
    return response["output"]