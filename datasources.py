"""
title: SQL Data Sources Tool (Apache Drill)
author: smonux
author_url:  https://github.com/smonux/open-webui-docker-execution
version: 0.0.4
"""

import requests
import json
import yaml
from pydantic import BaseModel, Field
from typing import Callable, Awaitable

event_data_template = """
---
<details>
  <summary>Execution: {ts}</summary>

##### Input:
```
{query}
```
##### Output:
```
{output}
```
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

        sql_columns = """
        select c.* from information_schema.`columns` c 
        """
        return await self.execute_sql( query = sql_columns,
                                 __event_emitter__  = __event_emitter__ )

    async def execute_sql(self, query : str,
                          __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """Executes a given SQL query on Apache Drill."""
        url = f"{self.drill_url}/query.json"
        payload = {"queryType": "SQL",
                   "query": query,
                   "autoLimit": self.max_rows}
        response = requests.post(url, json=payload)
        table = ''
        if response.status_code == 200:
            json_data = response.json()
            if "rows" in json_data:
                table = printTable(json_data["rows"], json_data.get("columns", None))
                del json_data["rows"]
            output = yaml.dump(json_data, default_flow_style=False)
            output = output + "\n--ROWS----\n\n" + table
        else:
            output = f"Error: {response.status_code} - {response.text}"

        return sql_output_template.format( output = output, query  = query )


    async def explain_plan_sql(self, query : str, 
                               __event_emitter__: Callable[[dict], Awaitable[None]]) -> str:
        """Executes a given SQL query on Apache Drill."""
        explain_query =  f"explain plan for {query}"

        if response.status_code == 200:
            jsretval = response.json()
            # we don't need it (too verbose)
            del jsretval["rows"][0]["json"]
            retval = json.dumps(jsretval)
        else:
            retval = f"Error: {response.status_code} - {response.text}"

        return retval 


