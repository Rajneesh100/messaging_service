# db_agent.py
import requests
import json
import psycopg2
from psycopg2.extras import RealDictCursor

class DBAgent:
    def __init__(self, 
                 model="llama3.2", 
                 base_url="http://localhost:11434",
                 db_host="localhost",
                 db_port=5432,
                 db_name="parser",
                 db_user="parser",
                 db_password="parser123"):
        
        self.model = model
        self.base_url = base_url
        
        # Database connection parameters
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'database': db_name,
            'user': db_user,
            'password': db_password
        }
        
        # Database schema info for LLM
        self.db_schema = """
Database Schema:

Tables:
1. orders
   - id (uuid, PK)
   - purchase_order_id (varchar, unique)
   - order_date (date)
   - buyer_name (varchar)
   - buyer_address (text)
   - supplier_name (varchar)
   - supplier_address (text)
   - currency (varchar, default 'USD')
   - tax_amount (numeric)
   - total_amount (numeric)
   - created_at (timestamp)
   - updated_at (timestamp)
   - completed (boolean, default false)
   
2. line_items
   - id (uuid, PK)
   - order_id (uuid, FK -> orders.id)
   - model_id (varchar)
   - item_code (varchar)
   - description (text)
   - color (varchar)
   - size (varchar)
   - quantity (integer)
   - unit_price (numeric)
   - amount (numeric)
   - delivery_date (date)
   - created_at (timestamp)

Relationships:
- orders.id is referenced by line_items.order_id (ON DELETE CASCADE)
- When user mentions order_id or purchase_order_id, they mean purchase_order_id
- To get item details for an order, JOIN line_items.order_id = orders.id
"""

    def get_db_connection(self):
        """Create and return a database connection"""
        return psycopg2.connect(**self.db_config)

    def db_decision_agent(self, user_msg):
        """Use LLM to determine if DB operations are needed and generate SQL queries"""
        print("[db_decision_agent] Starting...")
        
        prompt = f"""Analyze this user query: "{user_msg}"

{self.db_schema}

Does this query require database operations?

Read operations: SELECT queries to fetch data
Write operations: INSERT, UPDATE, DELETE queries to modify data

Reply with VALID JSON only (no extra text):
{{
    "read_required": true,
    "read_query": "SELECT * FROM orders WHERE ...",
    "write_required": false,
    "write_query": ""
}}

OR

{{
    "read_required": false,
    "read_query": "",
    "write_required": false,
    "write_query": ""
}}

Rules:
1. Generate valid PostgreSQL queries only
2. Use proper table and column names from the schema
3. For order lookups, use purchase_order_id column
4. For item details, JOIN orders and line_items tables
5. Use appropriate WHERE clauses based on user intent
6. For write operations, ensure data integrity and constraints

Examples:
Query: "Show me order PO-123" → {{"read_required": true, "read_query": "SELECT * FROM orders WHERE purchase_order_id = 'PO-123'", "write_required": false, "write_query": ""}}
Query: "Get latest 5 orders" → {{"read_required": true, "read_query": "SELECT * FROM orders ORDER BY order_date DESC LIMIT 5", "write_required": false, "write_query": ""}}
Query: "Mark order PO-123 as completed" → {{"read_required": false, "read_query": "", "write_required": true, "write_query": "UPDATE orders SET completed = true WHERE purchase_order_id = 'PO-123'"}}
Query: "What's the weather?" → {{"read_required": false, "read_query": "", "write_required": false, "write_query": ""}}

Now analyze the query above and respond with JSON only:"""
        
        coordinator_messages = [
            {"role": "system", "content": "You are a SQL query generator. Return ONLY valid JSON with SQL queries, no other text."},
            {"role": "user", "content": prompt}
        ]

        body = {
            "model": self.model,
            "messages": coordinator_messages,
            "stream": False,
            "keep_alive": "24h"
        }
        
        try:
            print(f"[db_decision_agent] Calling Ollama API...")
            r = requests.post(f"{self.base_url}/api/chat", json=body, timeout=30)
            r.raise_for_status()
            data = r.json()
            
            reply = data["message"]["content"]
            print(f"[db_decision_agent] Got reply: {reply}")
            
            # Parse the JSON response
            start = reply.find('{')
            end = reply.rfind('}') + 1
            if start != -1 and end > start:
                json_str = reply[start:end]
                print(f"[db_decision_agent] Extracted JSON: {json_str}")
                decision = json.loads(json_str)
                
                return decision
            else:
                print("[db_decision_agent] No valid JSON found in response")
                return {
                    "read_required": False,
                    "read_query": "",
                    "write_required": False,
                    "write_query": ""
                }
                
        except Exception as e:
            print(f"[db_decision_agent] ERROR: {e}")
            return {
                "read_required": False,
                "read_query": "",
                "write_required": False,
                "write_query": ""
            }

    def execute_read_query(self, query):
        """Execute a SELECT query and return results as JSON"""
        print(f"[execute_read_query] Executing: {query}")
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            # Convert to list of dicts (RealDictCursor returns RealDictRow objects)
            results_list = [dict(row) for row in results]
            
            print(f"[execute_read_query] Retrieved {len(results_list)} rows")
            return results_list
            
        except Exception as e:
            print(f"[execute_read_query] ERROR: {e}")
            return []

    def execute_write_query(self, query):
        """Execute an INSERT/UPDATE/DELETE query and return status"""
        print(f"[execute_write_query] Executing: {query}")
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(query)
            rows_affected = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"[execute_write_query] {rows_affected} rows affected")
            return {
                "success": True,
                "rows_affected": rows_affected,
                "message": f"Successfully executed write operation. {rows_affected} rows affected."
            }
            
        except Exception as e:
            print(f"[execute_write_query] ERROR: {e}")
            return {
                "success": False,
                "rows_affected": 0,
                "message": f"Error executing write operation: {str(e)}"
            }

    def process_db_request(self, user_msg):
        """Main method to process DB requests - decision + execution"""
        print("[process_db_request] Starting...")
        
        # Get decision from LLM
        decision = self.db_decision_agent(user_msg)
        
        context = ""
        
        # Execute read query if needed
        if decision.get("read_required") and decision.get("read_query"):
            read_results = self.execute_read_query(decision["read_query"])
            if read_results:
                context += f"\n\n[Database Query Results]:\n{json.dumps(read_results, indent=2, default=str)}\n"
        
        # Execute write query if needed
        if decision.get("write_required") and decision.get("write_query"):
            write_status = self.execute_write_query(decision["write_query"])
            context += f"\n\n[Database Write Operation]:\n{json.dumps(write_status, indent=2)}\n"
        
        return context if context else None


if __name__ == "__main__":
    # Test the DB agent
    db_agent = DBAgent()
    
    # Test query
    result = db_agent.process_db_request("Show me the latest 5 orders")
    print("\n=== Final Result ===")
    print(result)
