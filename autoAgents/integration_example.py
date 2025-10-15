# Integration example: Add this to your tio_agent.py

# At the top, import the DBAgent
from db_agent import DBAgent

# In LlamaSession.__init__, add:
class LlamaSession:
    def __init__(self, model="llama3.2", base_url="http://localhost:11434", 
                 enable_web_search=True, enable_db_access=True):
        self.model = model
        self.base_url = base_url
        self.enable_web_search = enable_web_search
        self.enable_db_access = enable_db_access
        
        # Initialize DB agent if enabled
        if self.enable_db_access:
            self.db_agent = DBAgent(model=model, base_url=base_url)
        
        self.history = [...]

    # Then in prepare_response method, add DB context gathering:
    def prepare_response(self, user_msg):
        print(f"[prepare_response] Starting with message: {user_msg}")
        user_msg_with_context = user_msg
        self.history.append({"role": "user", "content": user_msg})

        # 1. Web search context
        if self.enable_web_search:
            print("[prepare_response] Calling web_agent...")
            search_results = self.web_agent(user_msg)
            print(f"[prepare_response] Web agent returned: {search_results is not None}")
            
            if search_results:
                context = "\n\n[Web Search Results - Use these sources and INCLUDE their URLs in your response]:\n"
                for i, result in enumerate(search_results, 1):
                    context += f"\n{i}. Title: {result.get('title', 'No title')}\n"
                    context += f"   Content: {result.get('body', 'No description')}\n"
                    context += f"   URL: {result.get('href', 'No URL')}\n"
                
                context += "\n\nIMPORTANT: In your response, cite the sources by including the URLs like this: (Source: URL)\n"
                user_msg_with_context += context
        
        # 2. Database context
        if self.enable_db_access:
            print("[prepare_response] Calling db_agent...")
            db_context = self.db_agent.process_db_request(user_msg)
            print(f"[prepare_response] DB agent returned: {db_context is not None}")
            
            if db_context:
                user_msg_with_context += db_context
    
        # Return final response with all contexts
        return self.user_assistant(user_msg_with_context)


if __name__ == "__main__":
    session = LlamaSession(enable_web_search=True, enable_db_access=True)
    
    # Test DB query
    print(session.prepare_response("Show me the latest 5 orders"))
    print("-" * 50)
    
    # Test web search
    print(session.prepare_response("What's the latest news about AI?"))
    print("-" * 50)
    
    # Test combined (if query needs both)
    print(session.prepare_response("Show me orders from last week and tell me about recent market trends"))

