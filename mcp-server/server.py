"""
MCP Server for Multi-LLM Evaluation

This server exposes the LLM evaluation functionality via MCP protocol,
allowing other tools (like Claude Desktop) to compare LLM responses.
"""

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

# Backend API URL
BACKEND_URL = "http://localhost:8000/api"

# Create MCP server
server = Server("multi-llm-eval")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="list_providers",
            description="List all available LLM providers and their models",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="compare_llms",
            description="Compare responses from multiple LLMs for a given query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or prompt to send to all LLMs",
                    },
                    "providers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of provider IDs to use (e.g., ['groq', 'huggingface', 'ollama', 'gemini'])",
                    },
                    "models": {
                        "type": "object",
                        "description": "Optional: Mapping of provider ID to specific model name",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["query", "providers"],
            },
        ),
        Tool(
            name="get_evaluation_history",
            description="Get the history of previous LLM comparisons",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_evaluation",
            description="Get details of a specific evaluation by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "evaluation_id": {
                        "type": "string",
                        "description": "The ID of the evaluation to retrieve",
                    },
                },
                "required": ["evaluation_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Handle tool calls"""

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            if name == "list_providers":
                response = await client.get(f"{BACKEND_URL}/providers")
                response.raise_for_status()
                providers = response.json()

                # Format output
                output_lines = ["# Available LLM Providers\n"]
                for provider in providers:
                    status = "✓ Available" if provider["enabled"] else "✗ Unavailable"
                    output_lines.append(f"\n## {provider['name']} ({provider['id']})")
                    output_lines.append(f"Status: {status}")
                    output_lines.append("Models:")
                    for model in provider["models"]:
                        output_lines.append(f"  - {model}")

                return CallToolResult(
                    content=[TextContent(type="text", text="\n".join(output_lines))]
                )

            elif name == "compare_llms":
                query = arguments["query"]
                providers = arguments["providers"]
                models = arguments.get("models", {})

                response = await client.post(
                    f"{BACKEND_URL}/evaluate",
                    json={
                        "query": query,
                        "providers": providers,
                        "models": models,
                    },
                )
                response.raise_for_status()
                result = response.json()

                # Format output
                output_lines = [
                    f"# LLM Comparison Results\n",
                    f"**Query:** {result['query']}\n",
                    f"**Timestamp:** {result['timestamp']}\n",
                    "\n## Summary",
                    f"- **Fastest:** {result['comparison_summary']['fastest']}",
                    f"- **Highest Quality:** {result['comparison_summary']['highest_quality']}",
                    f"- **Most Cost Effective:** {result['comparison_summary']['most_cost_effective']}",
                    f"- **Best Overall:** {result['comparison_summary']['best_overall']}",
                    "\n## Detailed Responses\n",
                ]

                for resp in result["responses"]:
                    output_lines.append(f"### {resp['provider']} / {resp['model']}")
                    if resp.get("error"):
                        output_lines.append(f"**Error:** {resp['error']}")
                    else:
                        output_lines.append(f"**Metrics:**")
                        output_lines.append(f"- Latency: {resp['metrics']['latency_ms']:.0f}ms")
                        output_lines.append(f"- Tokens/sec: {resp['metrics']['tokens_per_second']:.1f}")
                        output_lines.append(f"- Quality Score: {resp['metrics']['quality_score']:.2%}")
                        output_lines.append(f"- Coherence: {resp['metrics']['coherence_score']:.2%}")
                        output_lines.append(f"- Relevance: {resp['metrics']['relevance_score']:.2%}")
                        output_lines.append(f"\n**Response:**\n{resp['response']}")
                    output_lines.append("\n---\n")

                return CallToolResult(
                    content=[TextContent(type="text", text="\n".join(output_lines))]
                )

            elif name == "get_evaluation_history":
                limit = arguments.get("limit", 10)
                response = await client.get(
                    f"{BACKEND_URL}/history",
                    params={"limit": limit},
                )
                response.raise_for_status()
                history = response.json()

                output_lines = ["# Evaluation History\n"]
                for item in history:
                    output_lines.append(f"- **ID:** {item['id']}")
                    output_lines.append(f"  Query: {item['query'][:50]}...")
                    output_lines.append(f"  Responses: {len(item['responses'])}")
                    output_lines.append(f"  Best: {item['comparison_summary']['best_overall']}")
                    output_lines.append("")

                return CallToolResult(
                    content=[TextContent(type="text", text="\n".join(output_lines))]
                )

            elif name == "get_evaluation":
                eval_id = arguments["evaluation_id"]
                response = await client.get(f"{BACKEND_URL}/evaluations/{eval_id}")
                response.raise_for_status()
                result = response.json()

                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=json.dumps(result, indent=2)
                    )]
                )

            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")]
                )

        except httpx.HTTPStatusError as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"API Error: {e.response.status_code} - {e.response.text}"
                )]
            )
        except httpx.RequestError as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Connection Error: {str(e)}. Make sure the backend is running."
                )]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")]
            )


async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
