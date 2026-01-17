import pickle
import pandas as pd
import torch
import time
import os
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

# Try to import Llama
try:
    from llama_cpp import Llama

    HAS_LLAMA_CPP = True
except ImportError:
    print("WARNING: 'llama_cpp' not found. Run 'pip install llama-cpp-python'")
    HAS_LLAMA_CPP = False

# ---------------------------
# 1. INITIALIZATION
# ---------------------------
print("--- MAX (Phi-2): Initializing ---")

# A. Load Movie Data
try:
    movies = pickle.load(open("Artifacts/movies_list.pkl", "rb"))
except FileNotFoundError:
    print("ERROR: 'Artifacts/movies_list.pkl' not found. Creating dummy data.")
    movies = pd.DataFrame(columns=["title", "tags", "overview", "genres", "bag_of_words"])

# Handle columns for SEARCHING (Creating the index)
if "bag_of_words" in movies.columns:
    movies["search_text"] = movies["bag_of_words"]
elif "tags" in movies.columns:
    movies["search_text"] = movies["tags"]
else:
    movies["search_text"] = movies["title"]

# B. Load Embedding Model (LOCALLY)
EMBEDDING_PATH = "models/all-MiniLM-L6-v2"
print(f"Loading embedding model from: {EMBEDDING_PATH}...")

if os.path.exists(EMBEDDING_PATH):
    embedder = SentenceTransformer(EMBEDDING_PATH)
    corpus_embeddings = embedder.encode(
        movies["search_text"].tolist(),
        convert_to_tensor=True
    )
else:
    print(f"CRITICAL ERROR: Folder '{EMBEDDING_PATH}' not found!")
    # Fallback to internet
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

# C. Load Phi-2 Brain (LOCALLY)
MODEL_PATH = "models/phi-2.Q4_K_M.gguf"
llm = None

if HAS_LLAMA_CPP:
    if os.path.exists(MODEL_PATH):
        print(f"Loading Phi-2 GGUF from {MODEL_PATH}...")
        try:
            llm = Llama(
                model_path=MODEL_PATH,
                n_ctx=2048,
                n_threads=6,
                n_batch=512,
                verbose=False
            )
            print("--- MAX: Phi-2 Brain Online ---")
        except Exception as e:
            print(f"Error loading model: {e}")
            llm = None
    else:
        print(f"WARNING: Model not found at {MODEL_PATH}")


# ---------------------------
# 2. HELPER FUNCTIONS
# ---------------------------

def retrieve_movies(query, top_k=3):
    """Finds top k semantic matches from the dataframe."""
    query_emb = embedder.encode(query, convert_to_tensor=True)
    scores = cos_sim(query_emb, corpus_embeddings)[0]
    top_results = torch.topk(scores, k=top_k)

    results = []
    for idx in top_results.indices:
        row = movies.iloc[int(idx)]

        # 1. Get Title
        title = row.get("title", "Unknown")

        # 2. Get Rich Context (Bag of Words has everything!)
        if "bag_of_words" in row:
            # This contains Overview + Genre + Actors
            info = str(row["bag_of_words"])
        elif "tags" in row:
            info = str(row["tags"])
        else:
            info = str(row.get("overview", "No info available"))

        # 3. Truncate carefully (Phi-2 limit)
        if len(info) > 400:
            info = info[:400] + "..."

        results.append({
            "title": title,
            "info": info
        })
    return results


def compress_context(retrieved_movies):
    """Formats the list of movies for the Prompt."""
    lines = []
    for m in retrieved_movies:
        line = f"Movie: {m['title']}\nDetails: {m['info']}\n"
        lines.append(line)
    return "\n---\n".join(lines)


def generate_response(query, context_str):
    """Generates the text using Phi-2 (Strict Mode)."""

    # 1. STRICT PROMPT: Explicitly tell it to be short and factual.
    prompt = f"""Instruct: You are Max, a movie recommender.
Context: {context_str}
User: {query}

Task: Recommend a movie from the Context.
Rules:
1. Keep it under 50 words.
2. Do NOT make up puzzles or stories.
3. Stop speaking immediately after your recommendation.

Output:"""

    # 2. GENERATE: Add 'repeat_penalty' and lower 'max_tokens'
    output = llm(
        prompt,
        max_tokens=100,  # Force it to be short (prevents 200s generation)
        temperature=0.6,  #
        repeat_penalty=1.1,  # Prevents it from getting stuck in loops
        stop=["Instruct:", "Output:", "User:", "\nUser", "Question:"]  # STOP SIGNALS
    )

    response_text = output["choices"][0]["text"].strip()

    # 3. SAFETY NET: Cut off any "run-on" text manually
    # If it generates a newline or starts a new paragraph, cut it there.
    if "\n" in response_text:
        response_text = response_text.split("\n")[0]

    return response_text


# ---------------------------
# 3. MAIN API FUNCTION
# ---------------------------

def get_local_response(user_query):
    start = time.time()

    try:
        # Step 1: Search
        retrieved = retrieve_movies(user_query)
        context_str = compress_context(retrieved)

        # DEBUG: See exactly what info is being fed to the AI
        print(f"\n[DEBUG] AI Context:\n{context_str}\n")

        if not retrieved:
            return "I couldn't find any movies like that in our database."

        # Step 2: Generate
        if llm:
            response = generate_response(user_query, context_str)
        else:
            response = f"I found these movies: {context_str}"

        elapsed = round(time.time() - start, 2)
        print(f"[MAX] Response generated in {elapsed}s")

        return response

    except Exception as e:
        print("ERROR:", e)
        return f"I found these movies: {context_str}"


# ---------------------------
# 4. INTERACTIVE TEST BLOCK
# ---------------------------
if __name__ == "__main__":
    print("\n" + "=" * 40)
    print("🎬 MAXMATE PROJECT (AI: MAX)")
    print("Type 'exit' to quit.")
    print("=" * 40 + "\n")

    while True:
        try:
            q = input("\nYou: ")
            if q.lower() in ["exit", "quit"]:
                print("Max: Goodbye! Happy watching! 🍿")
                break

            answer = get_local_response(q)
            print(f"Max: {answer}")

        except KeyboardInterrupt:
            print("\nMax: Goodbye!")
            break