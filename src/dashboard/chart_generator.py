import os
import re
from groq import Groq
from langchain_community.utilities import SQLDatabase
from datetime import datetime, timedelta
import json

def clean_sql_query(input_query: str) -> str:
    cleaned_query = re.sub(r'```(?:sql)?\n|\n```', '', input_query).strip()
    return cleaned_query

def generate_intelligent_dashboard(db: SQLDatabase, prompt: str):
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        schema = """
        CREATE TABLE employees (
            employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL CHECK (role IN ('Employee', 'Manager', 'CEO')),
            leave_balance INTEGER DEFAULT 20 CHECK (leave_balance >= 0),
            manager_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
        );
        CREATE TABLE projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE project_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id),
            UNIQUE (employee_id, project_id, start_date)
        );
        CREATE TABLE presence (
            presence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('Present', 'Absent', 'On Leave')),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            UNIQUE (employee_id, date)
        );
        CREATE TABLE leave_requests (
            leave_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            manager_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('Vacation', 'Sick', 'Personal', 'Disruption')),
            status TEXT NOT NULL CHECK (status IN ('Pending', 'Approved', 'Rejected')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
        );
        CREATE TABLE activity_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            hours INTEGER NOT NULL CHECK (hours >= 0),
            status TEXT NOT NULL CHECK (status IN ('Draft', 'Submitted', 'Approved', 'Rejected')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        """
        available_tables = db.get_table_names()
        current_date = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        chart_type = None
        prompt_lower = prompt.lower()
        if "as a pie chart" in prompt_lower:
            chart_type = "pie"
            prompt = prompt.replace("as a pie chart", "").replace("As a pie chart", "").strip()
        elif "as a bar chart" in prompt_lower:
            chart_type = "bar"
            prompt = prompt.replace("as a bar chart", "").replace("As a bar chart", "").strip()
        elif "as a line chart" in prompt_lower:
            chart_type = "line"
            prompt = prompt.replace("as a line chart", "").replace("As a line chart", "").strip()

        query_prompt = f"""
        Using the following SQLite database schema, generate a SQLite query for a dashboard based on: "{prompt}".
        {schema}
        - Available tables: {available_tables}.
        - Only use existing tables.
        - Return only the SQL query, no explanations or code blocks.
        - Generate a two-column result: non-numeric label (e.g., name, status), numeric value (e.g., COUNT, SUM).
        - Use JOINs and aggregations as needed.
        - For time-related queries, use date('now') or date('now', '-1 day'). Current date: {current_date}, yesterday: {yesterday}.
        - For pattern queries, include employee names for avatar display.
        """
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": query_prompt}]
        )
        query = clean_sql_query(response.choices[0].message.content)
        if not query:
            return {"error": "Empty SQL query generated."}

        used_tables = set(re.findall(r'\bFROM\s+([^\s;]+)|\bJOIN\s+([^\s;]+)', query, re.IGNORECASE))
        used_tables = {table for tup in used_tables for table in tup if table}
        if not all(table in available_tables for table in used_tables):
            return {"error": f"Query uses non-existent tables: {used_tables - set(available_tables)}"}

        result = db.run(query, fetch="all")
        result = eval(result) if isinstance(result, str) else result
        if not result:
            return {"error": "No data available for dashboard."}

        if not all(isinstance(row, tuple) and len(row) == 2 for row in result):
            return {"error": "Query result must have exactly two columns (label, value)."}

        try:
            float(result[0][1])
            labels = [str(row[0]) for row in result]
            values = [float(row[1]) for row in result]
        except (ValueError, TypeError):
            try:
                float(result[0][0])
                labels = [str(row[1]) for row in result]
                values = [float(row[0]) for row in result]
            except (ValueError, TypeError):
                return {"error": "One column must be numeric (value), the other non-numeric (label)."}

        if not chart_type:
            chart_prompt = f"""
            Suggest a chart type (bar, line, pie) for data with columns 'label' and 'value': {list(zip(labels, values))[:2]}.
            - Use pie for distributions (e.g., status, type).
            - Use bar for comparisons (e.g., counts by employee).
            - Use line for trends over time.
            Return only the chart type.
            """
            chart_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": chart_prompt}]
            )
            chart_type = chart_response.choices[0].message.content.strip().lower()
            if chart_type not in ["bar", "line", "pie"]:
                chart_type = "pie"

        # Generate avatars for employee names in labels
        avatars_html = ""
        for label in labels:
            if " " in label:  # Assume label is an employee name
                initials = "".join(word[0].upper() for word in label.split()[:2])
                color = ["#36A2EB", "#FF6384", "#FFCE56", "#4BC0C0", "#9966FF"][labels.index(label) % 5]
                avatars_html += f"""
                <div style="display: inline-block; margin: 10px; text-align: center;">
                    <svg width="50" height="50">
                        <circle cx="25" cy="25" r="20" fill="{color}"/>
                        <text x="25" y="25" fill="white" text-anchor="middle" dy=".3em" font-size="14">{initials}</text>
                    </svg>
                    <div>{label}</div>
                </div>
                """

        chart_config = {
            "type": chart_type,
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "Value",
                    "data": values,
                    "backgroundColor": ["#36A2EB", "#FF6384", "#FFCE56", "#4BC0C0", "#9966FF"][:len(labels)],
                    "borderColor": ["#2A8BBF", "#D44F6E", "#D4A53F", "#3A9C9C", "#7A52CC"][:len(labels)],
                    "borderWidth": 1
                }]
            },
            "options": {
                "scales": {
                    "y": {"beginAtZero": True, "title": {"display": True, "text": "Value"}},
                    "x": {"title": {"display": True, "text": "Label"}}
                } if chart_type != "pie" else {},
                "plugins": {
                    "legend": {"display": True},
                    "title": {"display": True, "text": prompt}
                }
            }
        }

        return {"chart_config": chart_config, "avatars_html": avatars_html}

    except Exception as e:
        return {"error": f"Error generating dashboard: {str(e)}"}