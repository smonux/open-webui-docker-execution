"""
title: Data Sources Tool (Apache Drill Integration)
author: smonux
author_url:  https://github.com/smonux/open-webui-docker-execution
version: 0.0.4
"""

import requests

class Tools:
    def __init__(self, drill_url="http://localhost:8047"):
        self.drill_url = drill_url

    def list_schema(self):
        """Lists all schemas available in Apache Drill."""
        url = f"{self.drill_url}/storage.json"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return f"Error: {response.status_code} - {response.text}"

    def execute_sql(self, query):
        """Executes a given SQL query on Apache Drill."""
        url = f"{self.drill_url}/query.json"
        payload = {"queryType": "SQL", "query": query}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            return f"Error: {response.status_code} - {response.text}"

    def show_execution_plan(self, query):
        """Shows the execution plan for a given SQL query on Apache Drill."""
        url = f"{self.drill_url}/query.json?options={'planner.add_plan': 'true'}"
        payload = {"queryType": "SQL", "query": query}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get('plan', "No plan found in response")
        else:
            return f"Error: {response.status_code} - {response.text}"
