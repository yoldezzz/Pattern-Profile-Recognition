import sqlite3
from datetime import datetime, timedelta

def create_test_db(db_path="src\\database\\test_db.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
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
    CREATE INDEX idx_employees_id ON employees(employee_id);

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
    CREATE INDEX idx_assignments_employee ON project_assignments(employee_id);

    CREATE TABLE presence (
        presence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('Present', 'Absent', 'On Leave')),
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
        UNIQUE (employee_id, date)
    );
    CREATE INDEX idx_presence_employee_date ON presence(employee_id, date);

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
    CREATE INDEX idx_reports_employee_date ON activity_reports(employee_id, date);

    CREATE TRIGGER enforce_single_ceo
    BEFORE INSERT ON employees
    FOR EACH ROW
    BEGIN
        SELECT CASE
            WHEN NEW.role = 'CEO' AND EXISTS (SELECT 1 FROM employees WHERE role = 'CEO')
            THEN RAISE(ABORT, 'Only one CEO is allowed.')
        END;
    END;

    CREATE TRIGGER update_leave_balance
    AFTER UPDATE ON leave_requests
    FOR EACH ROW
    WHEN NEW.status = 'Approved' AND OLD.status != 'Approved'
    BEGIN
        UPDATE employees
        SET leave_balance = leave_balance - (
            (julianday(NEW.end_date) - julianday(NEW.start_date)) + 1
        )
        WHERE employee_id = NEW.employee_id
        AND leave_balance >= (julianday(NEW.end_date) - julianday(NEW.start_date)) + 1;
    END;
    """)

    cursor.executescript("""
    INSERT INTO employees (name, email, role, leave_balance, manager_id) VALUES
        ('Alice Smith', 'alice@example.com', 'CEO', 20, NULL),
        ('Bob Johnson', 'bob@example.com', 'Manager', 20, 1),
        ('Carol White', 'carol@example.com', 'Employee', 18, 2),
        ('Dave Brown', 'dave@example.com', 'Employee', 15, 2),
        ('Eve Davis', 'eve@example.com', 'Employee', 20, 2);

    INSERT INTO projects (project_name, department) VALUES
        ('Project Alpha', 'Engineering'),
        ('Project Beta', 'Marketing'),
        ('Project Gamma', 'Finance');
    """)

    current_date = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    next_week_start = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    next_week_end = (datetime.now() + timedelta(days=9)).strftime('%Y-%m-%d')

    cursor.executescript(f"""
    INSERT INTO project_assignments (employee_id, project_id, start_date) VALUES
        (3, 1, '{current_date}'),
        (3, 2, '{current_date}'),
        (4, 1, '{current_date}'),
        (5, 3, '{current_date}');

    INSERT INTO presence (employee_id, date, status) VALUES
        (3, '{yesterday}', 'Present'),
        (4, '{yesterday}', 'On Leave'),
        (5, '{yesterday}', 'Present');

    INSERT INTO leave_requests (employee_id, manager_id, start_date, end_date, type, status) VALUES
        (3, 2, '{next_week_start}', '{next_week_end}', 'Vacation', 'Approved'),
        (4, 2, '{next_week_start}', '{next_week_end}', 'Sick', 'Pending'),
        (5, 2, '{next_week_start}', '{next_week_end}', 'Personal', 'Approved');

    INSERT INTO activity_reports (employee_id, project_id, date, hours, status) VALUES
        (3, 1, '{yesterday}', 8, 'Approved'),
        (3, 2, '{yesterday}', 4, 'Submitted'),
        (4, 1, '{yesterday}', 6, 'Draft'),
        (5, 3, '{yesterday}', 7, 'Approved');
    """)

    conn.commit()
    conn.close()
    print(f"Database created at {db_path}")

if __name__ == "__main__":
    create_test_db()