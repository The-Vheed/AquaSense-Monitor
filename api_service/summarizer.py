# llm_summarizer/summarizer.py
from typing import List

# Assuming common is in sys.path or accessible
from common.config import Config
from common.models import Anomaly

# from langchain_openai import ChatOpenAI
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate


class LLMSummarizer:
    """
    Handles LLM-based summarization of anomalies using LangChain and Ollama.
    This class is designed to be imported and used by other services.
    """

    def __init__(self):
        # Initialize the Ollama LLM client
        self.ollama_base_url = f"http://{Config.OLLAMA_HOST}:{Config.OLLAMA_PORT}"
        try:
            self.llm = Ollama(
                base_url=self.ollama_base_url,
                model=Config.LLM_MODEL_NAME,
                temperature=Config.LLM_TEMPERATURE,
                num_predict=Config.LLM_MAX_NEW_TOKENS,
            )
            self.status_llm = Ollama(
                base_url=self.ollama_base_url,
                model=Config.LLM_MODEL_NAME,
                temperature=0.1,
                num_predict=2,
            )

            # OpenAI used for speedy debugging
            # self.llm = ChatOpenAI(
            #     model="gpt-4o-mini",  # Use a specific model for ChatOpenAI
            #     temperature=Config.LLM_TEMPERATURE,
            #     max_completion_tokens=Config.LLM_MAX_NEW_TOKENS,
            # )
            # self.status_llm = ChatOpenAI(
            #     model="gpt-4o-mini",  # Use a specific model for ChatOpenAI
            #     max_completion_tokens=2,
            # )

            print(
                f"LLM Summarizer: Successfully connected to Ollama at {self.ollama_base_url}"
            )
        except Exception as e:
            print(
                f"LLM Summarizer: Could not connect to Ollama at {self.ollama_base_url}. Error: {e}"
            )
            self.llm = None  # Set to None if connection fails

        # Define the prompt template for anomaly summarization
        self.prompt_template = PromptTemplate(
            input_variables=["anomalies_data"],
            template="""You are an expert system for a water treatment facility.
            Analyze the following list of detected sensor anomalies and provide a concise, human-readable summary.
            Focus on the most important events and their impact. If no anomalies are present, state that.
            
            Your response must be as brief as possible, while still conveying concise analytics on the anomalies.
            
            Anomalies:
            {anomalies_data}
            
            Summary:""",
        )

        # Create an LLMChain only if LLM was initialized successfully
        # Using the new LCEL syntax for chaining
        self.llm_chain = self.prompt_template | self.llm

        # Create a simple prompt to get a 'Y' response
        self.status_prompt_template = PromptTemplate(
            input_variables=[], template="Reply with only the letter 'Y'."
        )
        self.status_chain = self.status_prompt_template | self.status_llm

        if self.llm_chain:
            print(
                f"LLM Summarizer initialized with Ollama model: {Config.LLM_MODEL_NAME} at {self.ollama_base_url}"
            )
        else:
            print(
                "LLM Summarizer initialized without a functional LLM chain due to prior errors."
            )

    async def generate_summary(self, anomalies: List[Anomaly]) -> tuple[bool, str]:
        """
        Generates a summary from a list of anomalies asynchronously.
        Returns a tuple: (success_status: bool, summary_text: str)
        """
        if not self.llm_chain:
            return (
                False,
                "LLM Summarizer is not active or not initialized properly. Cannot generate summary.",
            )

        if not anomalies:
            return True, "No anomalies detected in the recent period."

        # Format anomalies into a string for the LLM
        anomalies_str = ""
        for anomaly in anomalies:
            anomalies_str += f"- Type: {anomaly.type}, Timestamp: {anomaly.timestamp.isoformat()}, Sensor: {anomaly.sensor_id}, Parameter: {anomaly.parameter or 'N/A'}, Value: {anomaly.value or 'N/A'}, Message: {anomaly.message}\n"

        try:
            # Invoke the LLM chain asynchronously
            response = await self.llm_chain.ainvoke({"anomalies_data": anomalies_str})
            summary = (
                response.strip()
            )  # For LCEL, .ainvoke directly returns the string output

            # Check if summary is empty or only whitespace
            if not summary:
                return False, "Failed to generate summary: LLM returned empty response."

            return True, summary
        except Exception as e:
            print(f"Error generating LLM summary: {e}")
            return False, f"Error generating summary: {e}"

    async def check_llm_status(self) -> tuple[bool, str]:
        """
        Checks the LLM's responsiveness by asking it to reply with a single letter 'Y'.
        Returns a tuple: (success_status: bool, response_text: str)
        """
        if not self.llm_chain:
            return False, "LLM Summarizer is not active or not initialized properly."

        try:
            response = await self.status_chain.ainvoke({})
            cleaned_response = str(response).strip().upper()
            if "Y" in cleaned_response:
                print("LLM status check successful: Received 'Y'.")
                return True, "Y"
            else:
                print(
                    f"LLM status check failed: Received '{cleaned_response}' instead of 'Y'."
                )
                return False, f"Unexpected response: {cleaned_response}"
        except Exception as e:
            print(f"Error during LLM status check: {e}")
            return False, f"LLM status check failed due to error: {e}"
