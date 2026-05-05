from dotenv import load_dotenv
load_dotenv()
print("step 1 - dotenv OK")
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
print("step 2 - flask OK")
from supabase import create_client
from pinecone import Pinecone
from groq import Groq
from embedder import embed_document
from multi_agent import investigate_incident
from llm_logger import log_streaming_call, get_today_stats
print("step 3 - all imports OK")
import os, re, threading, json, tempfile
from datetime import datetime
app = Flask(__name__)
print("step 4 - app created")
from supabase import create_client
sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
pine_index = pc.Index(os.getenv('PINECONE_INDEX'))
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
print("step 5 - connections OK")
exec(open('app.py').read())
print("step 6 - app.py fully loaded")
input('Press Enter')