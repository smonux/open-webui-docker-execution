import requests
import json
import yaml
from pydantic import BaseModel, Field
from typing import Callable, Awaitable, List, Dict

event_data_template = """
---
<details>
  <summary>Execution: {ts}</summary>

##### Input:
{query}

##### Output:
{output}

---

</details>
"""

sql_output_template = """
<sql_execution>
<description>
This is the output of the SQL executed in an Apache Drill instance for
reference in the response. Use it to answer the query of the user.

The user know use have access to the tool and can inspect the executions,so there is point in avoiding talking about it.
</description>
<executed_sql>
{query}
</executed_sql>
<output>
{output}
</output>
</sql_execution>
"""

def printTable(myDict, colList=None):
   """ Pretty print a list of dictionaries (myDict) as a dynamically sized table.
   If column names (colList) aren't specified, they will show in random order.
   Author: Thierry Husson - Use it as you want but don't blame me.
   https://stackoverflow.com/questions/17330139/python-printing-a-dictionary-as-a-horizontal-table-with-headers
   """
   if not colList: colList = list(myDict[0].keys() if myDict else [])
   myList = [colList] # 1st row = header
   for item in myDict: myList.append([str(item[col] if item[col] is not None else '') for col in colList])
   colSize = [max(map(len,col)) for col in zip(*myList)]
   formatStr = ' | '.join(["{{:<{}}}".format(i) for i in colSize])
   myList.insert(1, ['-' * i for i in colSize]) # Seperating line
   acc = ""
   for item in myList: acc += formatStr.format(*item) + "\n"
   return acc

class Tools:
    class Valves(BaseModel):
        DRILL_URL: str = Field(
            default="http://localhost:8047",
            description="The URL of the Apache Drill instance."
        )
        MAX_ROWS : int = Field(
            default=100,
            description="Maximum rows returned"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.drill_url = self.valves.DRILL_URL
        self.max_rows = self.valves.MAX_ROWS

    async def get_structure(self,
                            __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """Get the definition of available datasources """
        sql_columns = "SELECT c.* FROM information_schema.columns c"
        return await self.execute_sql(query=sql_columns, __event_emitter__=__event_emitter__)

    async def list_databases(self, __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """List all available databases (schemas)"""
        query = "SHOW SCHEMAS"
        return await self.execute_sql(query=query, __event_emitter__=__event_emitter__)

    async def list_tables(self, database: str, __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """List all tables in a specified database"""
        query = f"SHOW TABLES IN `{database}`"
        return await self.execute_sql(query=query, __event_emitter__=__event_emitter__)

    async def describe_table(self, database: str, table: str, __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """Describe the schema of a specified table"""
        query = f"DESCRIBE `{database}`.`{table}`"
        return await self.execute_sql(query=query, __event_emitter__=__event_emitter__)

    async def get_sample_rows(self, database: str, table: str, limit: int = 10, __event_emitter__: Callable[[dict], Awaitable[None]] = None) -> str:
        """Retrieve sample rows from a specified table"""
        query = f"SELECT * FROM `{database}`.`{table}` LIMIT {limit}"
        return await self.execute_sql(query=query, __event_emitter__=__event_emitter__)

    async def get_table_metadata(self, database: str, table: str, __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """Fetch metadata for a specified table"""
        # Apache Drill doesn't provide a direct metadata query beyond DESCRIBE
        # You might need to execute multiple queries or parse information_schema
        query = f"""
        SELECT * FROM information_schema.tables
        WHERE table_schema = '{database}' AND table_name = '{table}'
        """
        return await self.execute_sql(query=query, __event_emitter__=__event_emitter__)

    async def execute_sql(self, query: str, __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """Executes a given SQL query on Apache Drill."""
        url = f"{self.drill_url}/query.json"
        payload = {
            "queryType": "SQL",
            "query": query,
            "autoLimit": self.max_rows
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            json_data = response.json()
            table = ''
            if "rows" in json_data:
                table = printTable(json_data["rows"], json_data.get("columns", None))
                del json_data["rows"]
            output = yaml.dump(json_data, default_flow_style=False)
            if table:
                output += "\n--ROWS----\n\n" + table
        except requests.exceptions.RequestException as e:
            output = f"Error: {str(e)}"
        
        return sql_output_template.format(output=output, query=query)

    async def explain_plan_sql(self, query: str, __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """Executes an EXPLAIN PLAN for a given SQL query on Apache Drill."""
        explain_query = f"EXPLAIN PLAN FOR {query}"
        return await self.execute_sql(query=explain_query, __event_emitter__=__event_emitter__)

    # Optionally, you can add more utility functions as needed
