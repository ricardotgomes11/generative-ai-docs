#
# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Test the vector database"""

import os
import sys
import google.generativeai as palm
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from chromadb.api.types import Document, Embedding, Documents, Embeddings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from ratelimit import limits, sleep_and_retry
import read_config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Set the directory path to locate the Chroma vector database
LOCAL_VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_stores/chroma")
COLLECTION_NAME = "docs_collection"
EMBEDDING_MODEL = None

IS_CONFIG_FILE = True
if IS_CONFIG_FILE:
    config_values = read_config.ReadConfig()
    LOCAL_VECTOR_DB_DIR = config_values.returnConfigValue("vector_db_dir")
    COLLECTION_NAME = config_values.returnConfigValue("collection_name")
    EMBEDDING_MODEL = config_values.returnConfigValue("embedding_model")

# Set a test question
QUESTION = "What are some differences between apples and oranges?"
NUM_RETURNS = 5

# Set up the PaLM API key from the environment
API_KEY = os.getenv("PALM_API_KEY")
if API_KEY is None:
    sys.exit("Please set the environment variable PALM_API_KEY to be your API key.")

# Select your PaLM API endpoint
PALM_API_ENDPOINT = "generativelanguage.googleapis.com"
palm.configure(api_key=API_KEY, client_options={"api_endpoint": PALM_API_ENDPOINT})

# Set up the path to the local LLM
# This value is used only when `EMBEDDINGS_TYPE` is set to `LOCAL`
LOCAL_LLM = os.path.join(BASE_DIR, "models/all-mpnet-base-v2")

# Use the PaLM API for generating embeddings by default
EMBEDDINGS_TYPE = "PALM"

# PaLM API call limit to 300 per minute
API_CALLS = 280
API_CALL_PERIOD = 60


# Create embed function for PaLM
# API call limit to 5 qps
@sleep_and_retry
@limits(calls=API_CALLS, period=API_CALL_PERIOD)
def embed_palm_api_call(text: Document) -> Embedding:
    if PALM_EMBEDDING_MODEL == "models/embedding-001":
        # Use the `embed_content()` method if it's the new Gemini embedding model.
        return palm.embed_content(model=PALM_EMBEDDING_MODEL, content=text)["embedding"]
    else:
        return palm.generate_embeddings(model=PALM_EMBEDDING_MODEL, text=text)[
            "embedding"
        ]


def embed_palm(texts: Documents) -> Embeddings:
    # Embed the documents using any supported method
    return [embed_palm_api_call(text) for text in texts]


# Initialize Rich console
ai_console = Console(width=160)
ai_console.rule("Fold")

chroma_client = chromadb.PersistentClient(path=LOCAL_VECTOR_DB_DIR)

if EMBEDDINGS_TYPE == "PALM":
    if EMBEDDING_MODEL is None:
        PALM_EMBEDDING_MODEL = "models/embedding-gecko-001"
    else:
        PALM_EMBEDDING_MODEL = EMBEDDING_MODEL
    emb_fn = embed_palm
else:
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=LOCAL_LLM
    )

collection = chroma_client.get_collection(
    name=COLLECTION_NAME, embedding_function=emb_fn
)

results = collection.query(query_texts=[QUESTION], n_results=NUM_RETURNS)

print("")
ai_console.print(Panel.fit(Markdown(f"Question: {QUESTION}")))
print("Results:")
print(results)
print("")

i = 0
for document in results["documents"]:
    for content in document:
        print(f"Content {str(i)}: ")
        ai_console.print(Panel.fit(Markdown(content)))
        source = results["metadatas"][0][i]
        this_id = results["ids"][0][i]
        distance = results["distances"][0][i]
        print("  source: " + source["source"])
        print("  URL: " + source["url"])
        print(f"  ID: {this_id}")
        print(f"  Distance: {str(distance)}")
        print("")
        i += 1
