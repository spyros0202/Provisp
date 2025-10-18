from django.http import JsonResponse
from django.shortcuts import redirect
from .graph.neo4j_connector import get_suggestions, get_node_by_id, universal_search, search_and_expand, run_generated_cypher
from .llm import call_llm, extract_search_plan
from django.core.mail import send_mail
from django.shortcuts import render

def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")

        full_message = f"From: {name} <{email}>\n\n{message}"

        try:
            send_mail(
                subject=f"New message from {name}",
                message=full_message,
                from_email="spyros0202@gmail.com",  # explicit sender
                recipient_list=["spyros0202@gmail.com"],
                fail_silently=False,
            )
            print("Email sent OK")  # should appear in terminal
            return render(request, "contact.html", {"success": True})
        except Exception as e:
            print("Email send error:", e)
            return render(request, "contact.html", {"error": True})

    return render(request, "contact.html")

def about(request):
    return render(request, "about.html")

def detail_view(request, node_id):
    node = get_node_by_id(node_id)

    if not node:
        return JsonResponse({"error": "Node not found"}, status=404)

    # Build category_status_list with ALL categories
    node_labels = set(node['labels'])  # labels that are "on"
    
    # Define all possible categories with their icons
    all_categories = [
        {"name": "Sheep", "icon": "fa-sheep", "is_on": "Sheep" in node_labels},
        {"name": "Farm", "icon": "fa-home", "is_on": "Farm" in node_labels},
        {"name": "Owner", "icon": "fa-user", "is_on": "Owner" in node_labels},
        {"name": "Health", "icon": "fa-heart", "is_on": "Health" in node_labels},
        {"name": "Breed", "icon": "fa-tag", "is_on": "Breed" in node_labels},
        {"name": "Vaccination", "icon": "fa-syringe", "is_on": "Vaccination" in node_labels},
    ]
    
    # Filter to only show categories that are relevant
    category_status_list = [cat for cat in all_categories if cat["is_on"] or any(label.lower() in cat["name"].lower() for label in node_labels)]

    return JsonResponse({
        "node": node,
        "category_status_list": category_status_list,
    })


def home(request):
    query = request.GET.get("q")
    if not query:
        return render(request, "home.html", {"data": [], "query": "", "page": 1})

    page = int(request.GET.get("page", "1"))
    page = max(1, page)

    data = universal_search(query=query)
    context = {
        "data": data,
        "query": query,
        "page": page,
    }
    return render(request, "home.html", context)

def autocomplete_view(request):
    partial = request.GET.get("q", "")
    results = get_suggestions(partial)
    return JsonResponse({"results": results})



def chat_view(request):
    if request.method != "GET":
        return JsonResponse({"error": "Invalid method"}, status=405)

    question = (request.GET.get("q", "") or "").strip()
    if not question:
        return JsonResponse({"error": "No question provided"}, status=400)

    # Reset session each chat to avoid cross-topic replies
    request.session.flush()
    history = [{"role": "user", "content": question}]

    plan = extract_search_plan(question)
    cypher = plan.get("cypher")
    retrieval = run_generated_cypher(cypher) if cypher else search_and_expand(question)

    answer_payload = call_llm(question, retrieval.get("text_context", ""), history)

    history.append({"role": "assistant", "content": answer_payload["answer"]})
    request.session["chat_history"] = history[-10:]
    request.session.modified = True

    return JsonResponse({
        "question": question,
        "answer": answer_payload["answer"],
        "source": answer_payload["source"],
        "facts_count": len(retrieval.get("facts", [])),
        "plan": plan,
    })


def qa_redirect_view(request):
    # Backward-compat redirect: /qa?q=... -> /chat?q=...
    if request.method == "GET":
        q = request.GET.get("q")
        if q:
            return redirect(f"/chat/?q={q}")
    return redirect("/chat/")
