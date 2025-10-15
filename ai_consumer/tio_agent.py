# llama_session.py
import requests
import json
from ddgs import DDGS



class LlamaSession:
    def __init__(self, model="llama3.2", base_url="http://localhost:11434", enable_web_search=True):
        self.model = model
        self.base_url = base_url
        self.session_id = None  # generated automatically by ollama
        self.enable_web_search = enable_web_search
        self.history = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant with access to web search for current information. Keep all your responses under 1500 characters. Be concise but informative. When you use web search results, cite them naturally in your response."
            }
        ]
    
    def search_web(self, query, max_results=3):
        """Search the web and return relevant results"""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                print(results)
                return results
        except Exception as e:
            print(f"Web search error: {e}")
            return []

    def web_agent(self, user_msg):
        print("[web_agent] Starting...")
        prompt= f"""Analyze this user query: "{user_msg}"

        Does this query need CURRENT/REAL-TIME information from the web (news, weather, prices, recent events, etc.)?

        Questions about general knowledge, math, coding, or advice = NO web search
        Questions about current events, latest news, today's weather, recent prices = YES web search

        Reply with VALID JSON only (no extra text):
        {{
            "needs_search": true,
            "keywords": "short specific search terms"
        }}

        OR

        {{
            "needs_search": false,
            "keywords": ""
        }}

        Examples:
        Query: "What's happening with France politics?" → {{"needs_search": true, "keywords": "France politics latest news"}}
        Query: "Explain how Python works" → {{"needs_search": false, "keywords": ""}}
        Query: "Weather today in Paris" → {{"needs_search": true, "keywords": "Paris weather today"}}

        Now analyze the query above and respond with JSON only:"""
                
        # Don't add the coordinator prompt to history - use it in a separate call
        coordinator_messages = [
            {"role": "system", "content": "You are a decision agent. Return ONLY valid JSON, no other text."},
            {"role": "user", "content": prompt}
        ]

        body = {
            "model": self.model,
            "messages": coordinator_messages,
            "stream": False,
            "keep_alive": "24h"
        }
        
        try:
            print(f"[web_agent] Calling Ollama API...")
            r = requests.post(f"{self.base_url}/api/chat", json=body, timeout=30)
            r.raise_for_status()
            data = r.json()
            
            # Get web_agent response
            reply = data["message"]["content"]
            print(f"[web_agent] Got reply: {reply}")
            # Don't pollute main conversation history with internal agent decisions
        except Exception as e:
            print(f"[web_agent] ERROR: {e}")
            return None
        # Parse the JSON response
        try:
            # Extract JSON from response (handle cases where LLM adds extra text)
            start = reply.find('{')
            end = reply.rfind('}') + 1
            if start != -1 and end > start:
                json_str = reply[start:end]
                print(f"[web_agent] Extracted JSON: {json_str}")
                decision = json.loads(json_str)
                
                needs_search = decision.get("needs_search", False)
                keywords = decision.get("keywords", "")
                
                print(f"[web_agent] Decision: needs_search={needs_search}, keywords='{keywords}'")
                
                if needs_search and keywords:
                    print(f"[web_agent] Performing search with keywords: '{keywords}'")
                    return self.search_web(keywords)
                else:
                    print(f"[web_agent] No search needed")
                    return None
        except Exception as e:
            print(f"[web_agent] Error parsing web agent response: {e}")
        
        return None
        



    def prepare_response(self, user_msg):
        print(f"[prepare_response] Starting with message: {user_msg}")
        user_msg_with_context = user_msg
        self.history.append({"role": "user", "content": user_msg})

        # can be n number of such methods and we will gather all the context from each sub tasks right now im focused on web agent only
        if self.enable_web_search:
            print("[prepare_response] Calling web_agent...")
            search_results = self.web_agent(user_msg)
            print(f"[prepare_response] Web agent returned: {search_results is not None}")
        else:
            search_results = None

        if search_results:
            # Format search results as context
            context = "\n\n[Web Search Results - Use these sources and INCLUDE their URLs in your response]:\n"
            for i, result in enumerate(search_results, 1):
                context += f"\n{i}. Title: {result.get('title', 'No title')}\n"
                context += f"   Content: {result.get('body', 'No description')}\n"
                context += f"   URL: {result.get('href', 'No URL')}\n"
            
            context += "\n\nIMPORTANT: In your response, cite the sources by including the URLs like this: (Source: URL)\n"
            
            # Add search context to the user message
            user_msg_with_context = user_msg + context
    
        # Return final response with context
        return self.user_assistant(user_msg_with_context)

    def user_assistant(self, user_msg_with_context):
        print("[user_assistant] Starting...")
        # Update the last user message with context (if web search added info)
        if self.history[-1]["role"] == "user":
            self.history[-1]["content"] = user_msg_with_context
        
        body = {
            "model": self.model,
            "messages": self.history,
            "stream": False,
            "keep_alive": "24h"
        }
        
        try:
            print("[user_assistant] Calling Ollama API...")
            r = requests.post(f"{self.base_url}/api/chat", json=body, timeout=30)
            r.raise_for_status()
            data = r.json()
            # extract the model's message
            reply = data["message"]["content"]
            self.history.append({"role": "assistant", "content": reply})
            print(f"[user_assistant] Got reply: {reply}")
            return reply
        except Exception as e:
            print(f"[user_assistant] ERROR: {e}")
            return "Sorry, I encountered an error processing your request."

    def chat(self, user_msg):
        """Main entry point for chat - delegates to prepare_response"""
        return self.prepare_response(user_msg)


if __name__ == "__main__":
    # Test code - only runs when script is executed directly
    session = LlamaSession()
    # print(session.chat("i'm Rajneesh who are you"))
    # print("--------------")
    # print(session.chat("remember my name?"))
    # print("--------------")
    print(session.chat("what is going on with France politics? who is going to be a new prime minister of France, latest development in 2025"))
