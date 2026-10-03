import os
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
from supabase import create_client, Client
from backend.tools import execute_python_code


# 1. Load env and disable internal CrewAI telemetry
load_dotenv(find_dotenv(), override=True)
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_DISABLE_TRACKING"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "0" 
os.environ["OTEL_SDK_DISABLED"] = "true"

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from crewai import Agent, Task, Crew, LLM

# 2. Import LangSmith's traceable decorator
from langsmith import traceable

app = FastAPI(title="AutoDev AI Engine")
langsmith_project = os.environ.get("LANGSMITH_PROJECT", "AutoDev-AI-Phase3")

class CodeRequest(BaseModel):
    requirement: str
class SaveCodeRequest(BaseModel):
    user_prompt: str
    router_decision: str
    final_code: str
def check_guardrail(prompt: str) -> bool:
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        system_instruction = """
        You are a strict security guardrail for a Python Code Generator. 
        Your ONLY job is to evaluate the user's prompt and respond with EXACTLY 'VALID' or 'INVALID'.
        
        Rules for VALID:
        - The user explicitly asks to write, generate, modify, or fix Python code for a legitimate, safe software task.
        
        Rules for INVALID:
        - Malicious/Security Risk: Asking for scripts to hack, exploit, bypass security, scrape illegally, or perform destructive actions (e.g., malware, system deletion).
        - Conceptual/Theory: Asking "what is X", "explain Y", or general computer science theory without asking to generate a script.
        - Out of Scope: Recipes, general knowledge, or non-programming tasks.
        
        Respond with ONLY 'VALID' or 'INVALID'. No other words, no punctuation.
        """
        response = model.generate_content(f"{system_instruction}\n\nUser Prompt: {prompt}")
        result = response.text.strip().upper()
        
        return result == "VALID"
    except Exception as e:
        print(f"Guardrail Error: {e}")
        return True

def get_embedding(text: str) -> list:
    """
    Converts text into a 3072-dimensional vector using Gemini embedding model.
    """
    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        result = genai.embed_content(
            model="models/gemini-embedding-2",
            content=text,
            task_type="retrieval_document"
        )
        return result['embedding']
    except Exception as e:
        print(f"Embedding Error: {e}")
        return []

# 3. Wrap CrewAI executions in LangSmith @traceable decorators
@traceable(name="Router_Decision", project_name=langsmith_project)
async def run_router(crew):
    return await crew.kickoff_async()

@traceable(name="Code_Generation_And_QA", project_name=langsmith_project)
async def run_execution_crew(crew):
    return await crew.kickoff_async()

@app.post("/api/generate-code")
async def generate_code(request: CodeRequest):
    is_valid_prompt = check_guardrail(request.requirement)
    
    if not is_valid_prompt:
        return {
            "status": "rejected", 
            "message": "Guardrail Alert: This prompt is out of scope. Please ask a question related to software development or coding."
        }
    try:
        print("Generating vector embedding for the user requirement...")
        prompt_embedding = get_embedding(request.requirement)
        
        if prompt_embedding:
            print("Vector generated successfully. Querying Supabase for semantic matches...")
            # Similarity threshold set to 0.75 for cache matching
            cache_result = supabase.rpc(
                'match_prompts',
                {'query_embedding': prompt_embedding, 'match_threshold': 0.60, 'match_count': 1}
            ).execute()
            
            print(f"Supabase RPC Result: {cache_result.data}")
            
            if cache_result.data and len(cache_result.data) > 0:
                print("CACHE HIT: Semantic match found in database.")
                cached_data = cache_result.data[0]
                return {
                    "status": "success",
                    "code": cached_data['response_code'],
                    "router_decision": "Supabase Cache"
                }
            else:
                print("CACHE MISS: No matching prompt found above the 0.75 similarity threshold.")
        else:
            print("ERROR: Failed to generate prompt embedding.")
    except Exception as e:
        print(f"Cache mechanism failed: {e}")
    # ==================================================
    # ==================================================
        # Fallback to CrewAI generation if cache fails or no match is found
        
    try:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        gemini_llm = LLM(
            model="gemini/gemini-2.5-flash",
            api_key=gemini_api_key,
            temperature=0.0
        )
        
        autodev_llm = LLM(
            model="openai/autodev-mistral", 
            base_url="https://sarcasm-xbox-earphone.ngrok-free.dev/v1", 
            api_key="sk-dummy-key"
        )

        # ---------------------------------------------------------
        # 1. THE ROUTER AGENT (GATEKEEPER)
        # ---------------------------------------------------------
        router_agent = Agent(
            role="Technical Lead & Task Router",
            goal="Analyze the complexity of a coding request and route it to the appropriate execution engine.",
            backstory="You are a system architect. You evaluate requirements and assign simple tasks to the fast local Mistral model, and complex algorithms to the powerful Gemini model. You strictly output one word without punctuation.",
            llm=gemini_llm,
            allow_delegation=False,
            verbose=True
        )
        
        router_task = Task(
            description=(
                f"Analyze the following user requirement: '{request.requirement}'\n\n"
                "RULES:\n"
                "1. If it involves basic string manipulation, standard API endpoints, or simple logic, output exactly: MISTRAL\n"
                "2. If it involves deep recursion, complex data structure parsing, or advanced algorithms, output exactly: GEMINI\n\n"
                "Return ONLY the word MISTRAL or GEMINI. No other text."
            ),
            expected_output="A single word: either MISTRAL or GEMINI.",
            agent=router_agent
        )
        
        router_crew = Crew(agents=[router_agent], tasks=[router_task], verbose=False,share_crew=False)
        
        # Call the traceable function instead of direct kickoff
        routing_decision_obj = await run_router(router_crew)
        routing_decision = str(routing_decision_obj).strip().upper()

        # ---------------------------------------------------------
        # 2. DYNAMIC WORKFLOW EXECUTION
        # ---------------------------------------------------------
        qa_agent = Agent(
            role="Lead QA Engineer",
            goal="Critically evaluate code by executing it. If it fails, delegate back with specific instructions.",
            backstory="Strict code evaluator checking for edge cases and logic errors. You MUST use the provided execution tool to verify code.",
            llm=gemini_llm,
            tools=[execute_python_code],
            allow_delegation=True,
            verbose=True
        )
        
        review_task_description = (
            f"Original User Requirement: '{request.requirement}'\n\n"
            "Critically review the provided Python code. You MUST use the 'Python Code Executor' tool to run the code and verify it works. "
            "If the execution fails or throws an error, delegate back to the Coder with the exact error traceback and specific fix instructions. "
            "If the Coder fails repeatedly, write the correct Python code YOURSELF, test it, and output the final working code. "
            "If the code executes successfully without errors and meets the requirements, output the final code."
        )

        if "MISTRAL" in routing_decision:
            coder_agent = Agent(
                role="Senior Python Developer",
                goal="Write accurate Python code based on requirements.",
                backstory="Elite AI engineer outputting working Python code.",
                llm=autodev_llm,
                allow_delegation=False,
                max_iter=5,
                verbose=True
            )
            
            coding_task = Task(
                description=f"User Requirement: '{request.requirement}'\n\nReturn ONLY the working code.",
                expected_output="A valid Python code block.",
                agent=coder_agent
            )
            
            review_task = Task(
                description=review_task_description,
                expected_output="Final, fully verified Python code block.",
                agent=qa_agent
            )
            
            execution_crew = Crew(agents=[coder_agent, qa_agent], tasks=[coding_task, review_task], verbose=True,share_crew=False)

        else:
            expert_coder_agent = Agent(
                role="Principal Python Architect",
                goal="Write complex algorithmic Python code perfectly on the first try.",
                backstory="You handle the most difficult logic challenges that smaller models cannot parse.",
                llm=gemini_llm,
                allow_delegation=False,
                verbose=True
            )
            
            expert_coding_task = Task(
                description=f"User Requirement: '{request.requirement}'\n\nReturn ONLY the working code.",
                expected_output="A valid Python code block.",
                agent=expert_coder_agent
            )
            
            execution_crew = Crew(agents=[expert_coder_agent], tasks=[expert_coding_task], verbose=True)

        # Call the traceable function instead of direct kickoff
        final_result_obj = await run_execution_crew(execution_crew)
        
        final_result = str(final_result_obj).replace("```python", "").replace("```", "").strip()
        
        return {
            "status": "success",
            "router_decision": routing_decision,
            "code": final_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/save-code")
async def save_code(request: SaveCodeRequest):
    try:
         response=supabase.table('code_logs').insert({
         "user_prompt": request.user_prompt,
         "router_decision": request.router_decision,
         "final_code": request.final_code
         }).execute()
         prompt_embedding = get_embedding(request.user_prompt)
         if prompt_embedding:
            supabase.table('semantic_cache').insert({
                "prompt": request.user_prompt,
                "response_code": request.final_code,
                "embedding": prompt_embedding
            }).execute()
         return {"status": "success", "message": "Code successfully saved to Supabase!"}
    except Exception as e:
       raise HTTPException(status_code=500, detail=str(e))