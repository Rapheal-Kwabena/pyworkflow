import sqlite3
from pyworkflow import Workflow
from pyworkflow.plugins.database import DatabasePlugin
from pyworkflow.plugins import registry


def test_database_plugin_integration():
    # Setup database connection
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    cursor.execute("INSERT INTO users (name) VALUES ('Alice')")
    cursor.execute("INSERT INTO users (name) VALUES ('Bob')")
    conn.commit()

    # Register and setup DatabasePlugin
    db_plugin = DatabasePlugin()
    db_plugin.setup(connection=conn)
    registry.register(db_plugin)

    # Build workflow
    wf = Workflow("DB Test")
    db_task = db_plugin.make_task("FetchUsers", "SELECT * FROM users ORDER BY name")
    wf.add_task(db_task)

    report = wf.run()
    assert report.success is True

    results = wf.tasks["FetchUsers"].output
    assert len(results) == 2
    assert results[0]["name"] == "Alice"
    assert results[1]["name"] == "Bob"

    conn.close()
