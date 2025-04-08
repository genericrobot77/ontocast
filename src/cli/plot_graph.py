from src.agent import create_agent_graph
import re
from pathlib import Path


def update_mermaid_graph_in_markdown(file_path: str, new_graph: str):
    md_path = Path(file_path)
    content = md_path.read_text()

    # Regex pattern to find "### Agent graph" followed by a mermaid block
    pattern = r"(### Agent graph\s+```mermaid\n)(.*?)(\n```)"
    replacement = r"\1" + new_graph + r"\3"

    if re.search(pattern, content, flags=re.DOTALL):
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        print("✅ Replaced existing Mermaid block.")
    else:
        # Append new section at the end
        new_section = f"\n\n### Agent graph\n\n```mermaid\n{new_graph}\n```"
        new_content = content + new_section
        print("➕ Appended new Mermaid block at the end.")

    md_path.write_text(new_content)
    print(f"📄 Updated {file_path}")


frontmatter_config = {
    "config": {
        "theme": "base",
        "look": "handDrawn",
        "themeVariables": {
            "primaryColor": "#FFF3E0",
            "primaryBorderColor": "#143642",
            "primaryTextColor": "#372237",
            "lineColor": "#FFAB91",
            "fontFamily": "'Architects Daughter', cursive",
            "fontSize": "20px",
        },
        "flowchart": {"curve": "basis", "htmlLabels": True, "useMaxWidth": True},
    }
}

# Get the graph and save it as PNG
output_path = "graph.png"
app = create_agent_graph()
graph = app.get_graph()
mmd_data = graph.draw_mermaid(frontmatter_config=frontmatter_config)

# Save the PNG data to a file
# with open("graph.mmd", "w") as f:
#     f.write(mmd_data)
mmd_data = mmd_data.replace("__start__", "START").replace("__end__", "END")
update_mermaid_graph_in_markdown("README.md", mmd_data)


# from langchain_core.runnables.graph import MermaidDrawMethod

# png_data = graph.draw_mermaid_png(
#     draw_method=MermaidDrawMethod.API,
#     frontmatter_config=frontmatter_config,
#     padding=20,
# )

# with open(output_path, "wb") as f:
#     f.write(png_data)
