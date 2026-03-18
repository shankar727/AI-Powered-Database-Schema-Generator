from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json
import re
import subprocess
import time
import requests
from typing import Dict
from langchain_core.prompts import PromptTemplate
from langchain_community.llms import Ollama
import psycopg2
from psycopg2 import Error as PgError
import pymysql
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this for production

# Initialize Ollama
llm = Ollama(
    model="gemma3:4b",
    temperature=0.3,
    num_ctx=2000,
    timeout=120
)

# ==============================================
# OLLAMA SERVER MANAGEMENT
# ==============================================

def is_ollama_installed():
    try:
        subprocess.run(["ollama", "--version"],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,
                       check=True)
        return True
    except:
        return False

def start_ollama_server():
    try:
        if os.name == 'nt':
            subprocess.Popen(["ollama", "serve"],
                             creationflags=subprocess.CREATE_NEW_CONSOLE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        else:
            subprocess.Popen(["ollama", "serve"],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             start_new_session=True)
        return True
    except Exception as e:
        return False

def check_server_ready(timeout=15):
    for i in range(timeout):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            time.sleep(1)
    return False

def ensure_ollama_running():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        pass

    if not start_ollama_server():
        return False

    return check_server_ready()

# ==============================================
# DATABASE CONNECTION FUNCTIONS
# ==============================================

def get_mysql_connection():
    try:
        connection = mysql.connector.connect(
            host=session.get('mysql_host'),
            user=session.get('mysql_user'),
            password=session.get('mysql_password'),
            database=session.get('mysql_database')
        )
        return connection
    except Error as e:
        return None

def get_postgres_connection():
    try:
        connection = psycopg2.connect(
            host=session.get('postgres_host'),
            user=session.get('postgres_user'),
            password=session.get('postgres_password'),
            dbname=session.get('postgres_database'),
            port=session.get('postgres_port', '5432')
        )
        return connection
    except PgError as e:
        return None

def execute_mysql_queries(queries):
    connection = get_mysql_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        for query in queries.split(';'):
            if query.strip():
                cursor.execute(query)
        connection.commit()
        return True
    except Error as e:
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def execute_postgres_queries(queries):
    connection = get_postgres_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        for query in queries.split(';'):
            if query.strip():
                cursor.execute(query)
        connection.commit()
        return True
    except PgError as e:
        return False
    finally:
        if connection:
            cursor.close()
            connection.close()

# ==============================================
# SCHEMA GENERATION FUNCTIONS
# ==============================================

schema_prompt = PromptTemplate(
    input_variables=["description"],
    template="""
You are a database design expert. Generate a detailed database schema in JSON format ONLY based on:
- Application description: {description}

Output MUST be a SINGLE VALID JSON object with this EXACT structure:
{{
    "tables": [
        {{
            "name": "table_name",
            "fields": [
                {{
                    "name": "field_name",
                    "type": "data_type",
                    "constraints": ["constraint1", "constraint2"]
                }}
            ],
            "relationships": [
                {{
                    "type": "1:1|1:N|M:N",
                    "related_to": "related_table",
                    "field": "foreign_key_field"
                }}
            ]
        }}
    ],
    "explanation": "Brief design explanation",
    "mysql_code": "Include valid MySQL CREATE TABLE statements for all tables, including PRIMARY and FOREIGN KEY constraints",
    "postgres_code": "Include valid PostgreSQL CREATE TABLE statements with specific PostgreSQL data types"
}}

IMPORTANT RULES:
1. Output ONLY the raw JSON with NO additional text
2. Ensure all quotes are straight double quotes (")
3. No trailing commas in arrays/objects
4. No comments or explanations outside the JSON
5. The "mysql_code" must be valid MySQL CREATE statements
6. The "postgres_code" must be valid PostgreSQL-specific CREATE statements
7. Both code fields must come at the end (after explanation)
8. All brackets and braces must be properly closed

BEGIN OUTPUT:
"""
)

def extract_json_from_response(response: str) -> Dict:
    cleaned = response.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    code_blocks = re.findall(r'(?:json)?\n(.*?)\n', cleaned, re.DOTALL)
    for block in code_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    start_idx = cleaned.find('{')
    end_idx = cleaned.rfind('}')
    if start_idx != -1 and end_idx != -1:
        potential_json = cleaned[start_idx:end_idx + 1]
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            try:
                fixed = re.sub(r',\s*([}\]])', r'\1', potential_json)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    return {"error": "Failed to extract valid JSON from response", "raw_response": cleaned[:500] + "..."}

def generate_schema(description: str) -> Dict:
    try:
        chain = schema_prompt | llm
        response = chain.invoke({
            "description": description
        })
        
        print(response)
        
        result = extract_json_from_response(response)
        if "error" in result:
            result["raw_response"] = response
        return result
    except Exception as e:
        return {"error": f"Schema generation failed: {str(e)}", "raw_response": str(e)}

def create_mermaid_diagram(schema: Dict) -> str:
    if not schema or schema.get('error'):
        return """erDiagram
    ERROR {
        string message "Invalid Schema"
    }"""
    
    try:
        diagram = ["erDiagram"]
        items = schema.get('tables', [])
        
        def simplify_type(field_type: str) -> str:
            """Simplify type names by removing length specifications"""
            if not isinstance(field_type, str):
                return str(field_type)
            if field_type.startswith("VARCHAR"):
                return "VARCHAR"
            if field_type.startswith("CHAR"):
                return "CHAR"
            if field_type.startswith("DECIMAL"):
                # Keep the basic type but remove precision/scale if present
                if "(" in field_type:
                    return "DECIMAL"
            return field_type
        
        # First pass: Create all entities with their attributes
        for item in items:
            if not isinstance(item, dict):
                continue
                
            table_name = item.get('name', 'unnamed')
            entity_lines = [f"    {table_name} {{"]
            
            for field in item.get('fields', []):
                if not isinstance(field, dict):
                    continue
                
                field_type = simplify_type(field.get('type', 'string'))
                field_name = field.get('name', 'unknown')
                
                # Handle constraints
                constraints = [c.upper() for c in field.get('constraints', [])]
                constraint_symbols = []
                if "PRIMARY KEY" in constraints:
                    constraint_symbols.append("PK")
                if "FOREIGN KEY" in constraints:
                    constraint_symbols.append('"FK"')
                if "UNIQUE" in constraints:
                    constraint_symbols.append("UK")
                if "NOT NULL" in constraints:
                    constraint_symbols.append('"NN"')
                
                constraint_str = f" {' '.join(constraint_symbols)}" if constraint_symbols else ""
                entity_lines.append(f"        {field_type} {field_name}{constraint_str}")
            
            entity_lines.append("    }")
            diagram.append("\n".join(entity_lines))
        
        # Second pass: Create all relationships
        relationships_added = set()
        
        for item in items:
            if not isinstance(item, dict):
                continue
                
            src_table = item.get('name', 'unknown')
            
            for rel in item.get('relationships', []):
                if not isinstance(rel, dict):
                    continue
                    
                dest_table = rel.get('related_to', 'unknown')
                rel_type = str(rel.get('type', '1:N')).upper().replace(":", "_").replace("-", "_")
                rel_field = rel.get('field', '')
                
                # Skip if relationship already added
                relationship_key = f"{src_table}-{dest_table}-{rel_field}"
                if relationship_key in relationships_added:
                    continue
                relationships_added.add(relationship_key)
                
                # Convert relationship type to Mermaid syntax
                if rel_type in ["1_1", "ONE_TO_ONE"]:
                    connector = " ||--|| "
                elif rel_type in ["1_N", "ONE_TO_MANY"]:
                    connector = " ||--o{ "
                elif rel_type in ["M_N", "N_M", "MANY_TO_MANY"]:
                    connector = " }o--o{ "
                else:
                    connector = " -- "
                
                diagram.append(f"    {src_table}{connector}{dest_table} : \"{rel_field}\"")
        
        print("\n".join(diagram))
        return "\n".join(diagram)
    except Exception as e:
        return f"""erDiagram
    ERROR {{
        string message "Error generating diagram: {str(e)}"
    }}"""

# ==============================================
# FLASK ROUTES
# ==============================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if not is_ollama_installed():
        return render_template('ollama_setup.html')
    
    if not ensure_ollama_running():
        return render_template('ollama_setup.html')
    
    if request.method == 'POST':
        session['mysql_host'] = request.form.get('mysql_host', 'localhost')
        session['mysql_user'] = request.form.get('mysql_user', 'root')
        session['mysql_password'] = request.form.get('mysql_password', '')
        session['mysql_database'] = request.form.get('mysql_database', 'my_database')
        session['postgres_host'] = request.form.get('postgres_host', 'localhost')
        session['postgres_user'] = request.form.get('postgres_user', 'postgres')
        session['postgres_password'] = request.form.get('postgres_password', '')
        session['postgres_database'] = request.form.get('postgres_database', 'postgres')
        session['postgres_port'] = request.form.get('postgres_port', '5432')
        
        db_type = request.form.get('db_type', 'MySQL')
        
        if 'test_connection' in request.form:
            if db_type == 'MySQL':
                conn = get_mysql_connection()
                if conn:
                    conn.close()
                    return render_template('index.html', success="✅ MySQL connection successful!")
                else:
                    return render_template('index.html', error="❌ MySQL connection failed!")
            else:
                conn = get_postgres_connection()
                if conn:
                    conn.close()
                    return render_template('index.html', success="✅ PostgreSQL connection successful!")
                else:
                    return render_template('index.html', error="❌ PostgreSQL connection failed!")
        
        if 'next_page' in request.form:
            return redirect(url_for('schema_design'))
    
    return render_template('index.html')

@app.route('/schema-design', methods=['GET', 'POST'])
def schema_design():
    if request.method == 'POST':
        if 'generate_schema' in request.form:
            description = request.form.get('description', '')
            
            if not description:
                return render_template('schema_design.html', error="Please provide an application description")
            
            schema = generate_schema(description)
            
            if schema.get('error'):
                return render_template('schema_design.html', 
                                      error=f"{schema['error']}\n\nRaw response preview:\n{schema.get('raw_response', 'None')}")
            
            session['generated_schema'] = schema
            mermaid_code = create_mermaid_diagram(schema)
            
            return render_template('schema_results.html', 
                                 schema=schema,
                                 mermaid_code=mermaid_code)
        
        if 'deploy_mysql' in request.form:
            schema = session.get('generated_schema')
            if schema and schema.get('mysql_code'):
                if execute_mysql_queries(schema['mysql_code']):
                    return render_template('schema_results.html', 
                                         schema=schema,
                                         mermaid_code=create_mermaid_diagram(schema),
                                         success="✅ Tables created successfully in MySQL!")
                else:
                    return render_template('schema_results.html', 
                                         schema=schema,
                                         mermaid_code=create_mermaid_diagram(schema),
                                         error="Failed to create tables in MySQL")
        
        if 'deploy_postgres' in request.form:
            schema = session.get('generated_schema')
            if schema and schema.get('postgres_code'):
                if execute_postgres_queries(schema['postgres_code']):
                    return render_template('schema_results.html', 
                                         schema=schema,
                                         mermaid_code=create_mermaid_diagram(schema),
                                         success="✅ Tables created successfully in PostgreSQL!")
                else:
                    return render_template('schema_results.html', 
                                         schema=schema,
                                         mermaid_code=create_mermaid_diagram(schema),
                                         error="Failed to create tables in PostgreSQL")
    
    return render_template('schema_design.html')

if __name__ == '__main__':
    app.run(debug=True)

