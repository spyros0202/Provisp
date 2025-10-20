# 🐑 Provato — Smart Farm Knowledge Assistant

Provato is an intelligent **farm management and query system** that connects **Neo4j graph databases** of farms, animals, and sensors with an **LLM-powered natural language interface**.  
It enables farmers, veterinarians, and agronomists to ask **free-form questions** (in English or Greek) and receive grounded answers directly from their farm data.Also this repo includes some Matlab Scripts (.m) that are describing SIRD epidemiological models , some ML simulations and  Python (.py) scripts for data processing procedures .

---

## 🚀 Features

- **Neo4j Graph Integration:** Stores farms, animals, devices, and meteorological data as connected nodes.  
- **Natural Language Chat:** Query the data using natural language via an LLM.  
- **Hybrid Search Engine:** Combines full-text Neo4j indexing with context-based retrieval.  
- **Dynamic Context Builder:** Expands relevant nodes and relationships for factual responses.  
- **Web Interface:** Simple Django + Bootstrap frontend with an interactive floating chat widget.  

---

## 🧠 Architecture Overview

```
User ↔ Django (views.py)
      ↕
LLM Layer (llm.py)
      ↕
Neo4j Graph (neo4j_connector.py)
      ↕
CSV Uploaders (uplading_neo4j.py)
```

## 🧩 Tech Stack

| Component | Technology |
|------------|-------------|
| Backend | Django 5.2 |
| Database | Neo4j AuraDB |
| Frontend | Bootstrap |
| Language | Python 3.11 |

---

## ⚙️ Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/provato.git
   cd provato
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export NEO4J_URI="neo4j+ssc://<your-instance>.databases.neo4j.io"
   export NEO4J_USER="neo4j"
   export NEO4J_PASS="<password>"
   export GOOGLE_API_KEY="<your-gemini-key>"
   ```

4. **Upload CSV data**
   ```bash
   python uplading_neo4j.py
   ```

5. **Run Django server**
   ```bash
   python manage.py runserver
   ```

6. Visit [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 💬 Example Queries

- “Which sheep belong to KFarm?”  
- “Show me all devices attached to animal 023.”  

---
