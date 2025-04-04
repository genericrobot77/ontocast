from langchain_core.runnables.graph import MermaidDrawMethod
from src.agent import create_agent_graph


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
png_data = graph.draw_mermaid_png(
    draw_method=MermaidDrawMethod.API,
    frontmatter_config=frontmatter_config,
    padding=20,
)

# Save the PNG data to a file
with open(output_path, "wb") as f:
    f.write(png_data)


mmd_data = graph.draw_mermaid(frontmatter_config=frontmatter_config)

# Save the PNG data to a file
with open("graph.mmd", "w") as f:
    f.write(mmd_data)
