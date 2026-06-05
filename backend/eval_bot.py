import asyncio
import time
import os
import pandas as pd
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from main import build_agent
from langchain.messages import HumanMessage

# Load environment variables
load_dotenv()

# Define the test evaluation dataset
EVALUATION_DATASET = [
    {
        "question": "Auf welchem Tabellenplatz steht Bayern München?",
        "ground_truth": "Bayern München steht auf Platz 1 der Bundesliga."
    },
    {
        "question": "Wann ist das nächste Spiel von Real Madrid?",
        "ground_truth": "Das nächste geplante Spiel von Real Madrid."
    },
    {
        "question": "Wer sind die Top-Scorer der Premier League?",
        "ground_truth": "Die Top-Scorer der Premier League Liga mit ihren erzielten Toren."
    },
    {
        "question": "Gib mir ein Rezept für einen Käsekuchen.",
        "ground_truth": "Der Assistent kann nur fussballbezogene Fragen beantworten."
    }
]

async def run_evaluation():
    """
    Runs the Ragas evaluation on the chatbot, measuring latency,
    faithfulness, and answer relevancy, and saves the results to a CSV.
    """
    print("Building LangChain football agent...")
    agent = await build_agent()
    
    questions = []
    responses = []
    contexts = []
    ground_truths = []
    durations = []

    print(f"Running {len(EVALUATION_DATASET)} evaluation queries...")
    for item in EVALUATION_DATASET:
        question = item["question"]
        print(f"\nEvaluating query: '{question}'")
        
        start_time = time.time()
        
        # Invoke agent
        try:
            result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
            reply = result["messages"][-1].content
            
            # Extract tool outputs as retrieved contexts
            tool_outputs = []
            for msg in result["messages"]:
                if msg.__class__.__name__ == "ToolMessage" or getattr(msg, "type", None) == "tool":
                    tool_outputs.append(str(msg.content))
            
            # If no tools were used, check with the Guard
            from main import _extract_used_tools, _run_guard
            used_tools = _extract_used_tools(reply)
            if not used_tools:
                reply_guard = await _run_guard(reply)
                if not reply_guard.allowed:
                    reply = reply_guard.message
            
            # Fallback if no tools were used
            if not tool_outputs:
                tool_outputs = ["No tools were used. Answer generated from internal knowledge or blocked by guard."]
                
        except Exception as e:
            reply = f"Error during execution: {str(e)}"
            tool_outputs = ["Execution failed"]

            
        duration = round(time.time() - start_time, 2)
        print(f"Response: '{reply[:100]}...' (took {duration}s)")
        
        questions.append(question)
        responses.append(reply)
        contexts.append(tool_outputs)
        ground_truths.append(item["ground_truth"])
        durations.append(duration)

    # Construct datasets.Dataset for Ragas
    data = {
        "user_input": questions,
        "response": responses,
        "retrieved_contexts": contexts,
        "reference": ground_truths
    }
    
    dataset = Dataset.from_dict(data)
    
    print("\nEvaluating dataset with Ragas metrics (faithfulness, answer_relevancy)...")
    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper

        evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))
        evaluator_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings())

        # Run evaluation (Ragas automatically reads OPENAI_API_KEY for grading)
        results = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy],
            llm=evaluator_llm,
            embeddings=evaluator_embeddings
        )

        
        # Convert to pandas DataFrame and append latency info
        df = results.to_pandas()
        df["duration_seconds"] = durations
        
        # Print summary
        avg_faithfulness = df["faithfulness"].mean()
        avg_relevance = df["answer_relevancy"].mean()
        avg_duration = df["duration_seconds"].mean()
        
        print("\n" + "="*40)
        print("EVALUATION RESULTS SUMMARY")
        print("="*40)
        print(f"Average Faithfulness:      {avg_faithfulness:.4f}")
        print(f"Average Answer Relevancy:  {avg_relevance:.4f}")
        print(f"Average Latency:           {avg_duration:.2f} seconds")
        print("="*40)
        
        # Save to CSV
        output_file = "bot_evaluation_results.csv"
        df.to_csv(output_file, index=False)
        print(f"Detailed logs saved to: {output_file}")
        
    except Exception as e:
        print(f"\nRagas evaluation failed: {e}")
        # Save raw answers even if evaluation fails
        df = pd.DataFrame(data)
        df["duration_seconds"] = durations
        df.to_csv("bot_raw_answers.csv", index=False)
        print("Raw answers saved to: bot_raw_answers.csv")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
