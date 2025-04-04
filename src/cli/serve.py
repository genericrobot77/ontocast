import os
import tempfile
from robyn import Robyn
from src.agent import process_document
from dotenv import load_dotenv
import click
import pathlib

app = Robyn(__file__)


@app.post("/process")
async def process_document_endpoint(request):
    try:
        # Get the uploaded file and ontology path
        data = await request.form()
        file = data.get("file")
        ontology_path = data.get("ontology_path")

        if not file or not ontology_path:
            return {"error": "file and ontology_path are required"}, 400

        # Create a temporary file to store the uploaded content
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write the uploaded file content to the temporary file
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Process the document
            result = process_document(temp_file_path, ontology_path)
            return result, 200
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)

    except Exception as e:
        return {"error": str(e)}, 500


@click.command()
@click.option("--env-path", type=click.Path(path_type=pathlib.Path), required=True)
def run(env_path: pathlib.Path):
    _ = load_dotenv(dotenv_path=env_path.expanduser())

    if "OPENAI_API_KEY" not in os.environ:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    port = int(os.getenv("PORT", "8000"))
    app.start(port=port)


if __name__ == "__main__":
    run()
