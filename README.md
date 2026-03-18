🚀 AI-Powered Database Schema Generator
An intelligent web application that generates complete database schemas (MySQL & PostgreSQL) from plain English descriptions using LLM (Ollama + Gemma3).
📌 Features
🧠 AI-based Schema Generation from text description
🗄️ Supports MySQL & PostgreSQL
🔗Automatically generates:
Tables
Fields
Relationships

📊 ER Diagram (Mermaid.js) visualization

⚡ Direct database deployment (execute queries)

🔄 Automatic Ollama server management

🛠️ Tech Stack

Backend: Flask (Python)

LLM: Ollama (Gemma3:4b)

Database: MySQL, PostgreSQL

Libraries:

LangChain

psycopg2

mysql-connector

requests

Frontend: HTML (Jinja templates)

Visualization: Mermaid.js

📂 Project Structure
├── app.py
├── templates/
│   ├── index.html
│   ├── schema_design.html
│   ├── schema_results.html
│   └── ollama_setup.html
├── static/
└── README.md
⚙️ Installation & Setup
1️⃣ Clone the repository
git clone https://github.com/your-username/AI-Powered-Database-Schema-Generator.git
cd AI-Powered-Database-Schema-Generator
2️⃣ Install dependencies
pip install -r requirements.txt
3️⃣ Install Ollama

Download from: https://ollama.com/

Then pull the model:

ollama pull gemma3:4b
4️⃣ Run the application
python app.py

App will start at:

http://127.0.0.1:5000
🧠 How It Works

User enters application description
Prompt sent to LLM (Gemma3 via Ollama)
Model generates:
JSON schema
MySQL queries
PostgreSQL queries
App:
Parses JSON
Displays schema
Generates ER diagram
User can:
Deploy schema directly to DB

📊 Example Input
E-commerce app with users, products, orders, and payments
Output:

Tables: Users, Products, Orders, Payments

Relationships:

User → Orders (1:N)

Order → Products (M:N)

🔌 Database Configuration
MySQL
Host
Username
Password
Database
PostgreSQL
Host
Username
Password
Database
Port

🚀 Key Functionalities
✅ Schema Generation
generate_schema(description)
✅ JSON Extraction
extract_json_from_response(response)
✅ ER Diagram
create_mermaid_diagram(schema)
✅ Database Execution
execute_mysql_queries(queries)
execute_postgres_queries(queries)
⚠️ Important Notes

Ensure Ollama is installed and running
Change secret_key before production
Validate DB credentials before deployment
AI output may need manual review for complex systems
🧩 Future Improvements
🌐 Add MongoDB support
🎨 Improve UI/UX
🔐 Authentication system
📥 Export schema as SQL file
☁️ Deploy on cloud (AWS/GCP)
🤝 Contributing
Fork the repo
Create your feature branch
Commit changes
Push to branch
Open Pull Request
📜 License
This project is licensed under the MIT License.
👨‍💻 Author

Shankar Kumar Yadav
