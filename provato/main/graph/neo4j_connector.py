from neo4j import GraphDatabase
import os


NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://53ed6a0b.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "")
NEO4J_DB = os.getenv("NEO4J_DATABASE", "neo4j")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


# --------------------- Universal Search ---------------------
def universal_search(query: str, limit: int = 20):
    """
    Search all nodes using the fulltext index 'everythingIndex'.
    Returns basic node data (id, labels, properties, score).
    """
    with driver.session(database=NEO4J_DB) as session:
        result = session.run("""
            CALL db.index.fulltext.queryNodes("everythingIndex", $q)
            YIELD node, score
            RETURN elementId(node) AS neo4j_id,
                   labels(node) AS labels,
                   properties(node) AS props,
                   score
            ORDER BY score DESC
            LIMIT $limit
        """, {"q": query.lower(), "limit": limit})

        data = []
        for record in result:
            props = record["props"] or {}
            display_name = (
                props.get("name") or
                props.get("tag") or
                props.get("breed") or
                "(Unnamed)"
            )
            data.append({
                "neo4j_id": record["neo4j_id"],
                "labels": record["labels"],
                "props": props,
                "score": record["score"],
                "display_name": display_name,
            })
        return data


# --------------------- Autocomplete ---------------------
def get_suggestions(partial: str):
    """
    Returns up to 10 name suggestions matching a partial query.
    """
    if not partial:
        return []

    with driver.session(database=NEO4J_DB) as session:
        result = session.run("""
            MATCH (n)
            WHERE any(key IN ['name','tag','breed','owner']
                      WHERE toLower(toString(n[key])) CONTAINS $partial)
            WITH coalesce(n.name, n.tag, n.breed, n.owner) AS suggestion
            RETURN DISTINCT suggestion
            ORDER BY suggestion
            LIMIT 10
        """, {"partial": partial.lower()})
        return [r["suggestion"] for r in result if r["suggestion"]]


# --------------------- Single Node Lookup ---------------------
def get_node_by_id(node_id: str):
    with driver.session(database=NEO4J_DB) as session:
        result = session.run("""
            MATCH (n)
            WHERE elementId(n) = $id
            RETURN labels(n) AS labels, properties(n) AS props
        """, {"id": node_id})
        record = result.single()
        if not record:
            return None
        props = record["props"] or {}
        display_name = props.get("name") or props.get("tag") or "(Unnamed)"
        return {
            "labels": record["labels"],
            "props": props,
            "display_name": display_name,
        }


# --------------------- Relationships ---------------------
def get_node_with_rels(node_id: str):
    with driver.session(database=NEO4J_DB) as session:
        result = session.run("""
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $id
            RETURN type(r) AS rel_type,
                   elementId(m) AS related_id,
                   labels(m) AS related_labels,
                   properties(m) AS related_props
        """, {"id": node_id})

        rels = []
        for record in result:
            props = record["related_props"] or {}
            display_name = props.get("name") or props.get("tag") or props.get("breed") or "(Unnamed)"
            rels.append({
                "rel_type": record["rel_type"],
                "related_id": record["related_id"],
                "related_labels": record["related_labels"],
                "display_name": display_name,
            })
        return rels


# --------------------- Context Builder ---------------------
def search_and_expand(question: str, top_k: int = 5, neighbor_limit: int = 15):
    """
    Builds a rich grounded context from Neo4j for a natural language question.
    - Uses full-text search to find top_k relevant nodes.
    - Expands each node with relationships and key properties.
    Returns a dict with nodes, structured facts, and a text context for LLMs.
    """
    hits = universal_search(question, limit=top_k)
    if not hits:
        return {"nodes": [], "facts": [], "text_context": ""}

    facts, nodes_out = [], []

    with driver.session(database=NEO4J_DB) as session:
        for hit in hits:
            node_id = hit["neo4j_id"]
            node_labels = hit["labels"]
            node_props = hit["props"]
            display_name = hit.get("display_name")

            nodes_out.append({
                "neo4j_id": node_id,
                "labels": node_labels,
                "props": node_props,
                "display_name": display_name,
            })

            # Self facts
            for k, v in node_props.items():
                facts.append(f"{display_name} ({'|'.join(node_labels)}): {k} = {v}")

            # Relations
            rel_result = session.run("""
                MATCH (n)-[r]-(m)
                WHERE elementId(n) = $id
                RETURN type(r) AS rel_type,
                       elementId(m) AS related_id,
                       labels(m) AS related_labels,
                       properties(m) AS related_props
                LIMIT $limit
            """, {"id": node_id, "limit": neighbor_limit})

            for r in rel_result:
                rel_type = r["rel_type"]
                related_labels = r["related_labels"] or []
                related_props = r["related_props"] or {}
                related_name = related_props.get("name") or related_props.get("tag") or "(Unnamed)"

                facts.append(f"{display_name} -[{rel_type}]-> {related_name} ({'|'.join(related_labels)})")

                for key in ["breed", "age", "owner", "farm", "health_status", "last_vaccination"]:
                    if key in related_props:
                        facts.append(f"{related_name}: {key} = {related_props[key]}")

    text_context = "\n".join(facts)
    return {"nodes": nodes_out, "facts": facts, "text_context": text_context}


# --------------------- Precise Lookup ---------------------
def precise_lookup(plan: dict, limit: int = 5, neighbor_limit: int = 20):
    """
    Perform an exact search when the question has structure (from an LLM plan).
    """
    if not plan:
        return {"nodes": [], "facts": [], "text_context": ""}

    name = plan.get("name")
    labels = plan.get("labels", [])
    identifiers = plan.get("identifiers", {})
    fields = plan.get("fields", [])

    conditions, params = [], {}

    if name:
        conditions.append("(n.name = $name OR n.tag = $name OR n.breed = $name)")
        params["name"] = name

    for k, v in identifiers.items():
        if v:
            conditions.append(f"n.{k} = ${k}")
            params[k] = v

    if labels:
        label_conditions = [f"'{l}' IN labels(n)" for l in labels]
        conditions.append(f"({' OR '.join(label_conditions)})")

    if not conditions:
        return {"nodes": [], "facts": [], "text_context": ""}

    where_clause = " AND ".join(conditions)

    with driver.session(database=NEO4J_DB) as session:
        main_query = f"""
        MATCH (n)
        WHERE {where_clause}
        RETURN elementId(n) AS neo4j_id, labels(n) AS labels, properties(n) AS props
        LIMIT $limit
        """

        result = session.run(main_query, {**params, "limit": limit})
        nodes_out, facts = [], []

        for record in result:
            node_id = record["neo4j_id"]
            node_labels = record["labels"]
            props = record["props"] or {}
            display_name = props.get("name") or props.get("tag") or "(Unnamed)"

            nodes_out.append({
                "neo4j_id": node_id,
                "labels": node_labels,
                "props": props,
                "display_name": display_name,
            })

            for k, v in props.items():
                if not fields or k in fields:
                    facts.append(f"{display_name}: {k} = {v}")

            rels = session.run("""
                MATCH (n)-[r]-(m)
                WHERE elementId(n) = $id
                RETURN type(r) AS rel_type,
                       labels(m) AS related_labels,
                       properties(m) AS related_props
                LIMIT $limit
            """, {"id": node_id, "limit": neighbor_limit})

            for rel in rels:
                rel_type = rel["rel_type"]
                related_name = rel["related_props"].get("name") or rel["related_props"].get("tag") or "(Unnamed)"
                facts.append(f"{display_name} -[{rel_type}]- {related_name}")

        return {
            "nodes": nodes_out,
            "facts": facts,
            "text_context": "\n".join(facts),
        }

def run_generated_cypher(cypher: str, limit: int = 100):
    with driver.session(database=NEO4J_DB) as session:
        try:
            result = session.run(cypher)
        except Exception as e:
            return {"error": str(e), "facts": [], "text_context": ""}

        facts = []
        for r in result:
            for k, v in r.items():
                facts.append(f"{k}: {v}")
        return {"facts": facts, "text_context": "\n".join(facts)}
