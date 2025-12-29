import os, logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("businessflow")

@mcp.tool
async def create_folder(folder_path:str)->dict:
    """
    Create a folder at the specified location and return an execution status.

    Agent Tool Specification:
        Name: create_folder
        Description: Creates a directory or folder at the given path.
                     Returns a structured status dictionary with success or error details.
        Input Arguments:
            folder_path (str): Path where the folder or file should be created.
        Output:
            dict: {
                "STATUS": bool,       # True if creation succeeded, False otherwise
                "PATH": str            # Full path of the created file/folder
            }

    Behavior:
        - Validates the input path and constructs the full target path.
        - Creates any missing directories when creating a file.
        - Overwrites nothing; if the target already exists, marks the operation as successful.
        - Captures and reports exceptions in the status dictionary.

    """
    WORKSPACE_DIR=os.environ.get("WORKSPACE_DIR")
    folder_path = WORKSPACE_DIR+os.sep+folder_path
    if not safe_join(WORKSPACE_DIR,folder_path):
        return {
            "STATUS": "FAILURE",
            "PATH": f"{folder_path} outside working directory. Do not use eacape sequence in your directory path"
        }
    try:
        os.makedirs(folder_path,exist_ok=True)
    except (FileExistsError,Exception) as e:
        logger.error("File exsist {folder_path}")
        #print(f"File exsist {folder_path}",file=sys.stderr)
    return {
        "STATUS": "SUCCESS",
        "PATH": f"{folder_path}"
    }
        
@mcp.tool
async def create_file(parent_folder_path:str,file_name:str,content:str)->dict:
    """
    Create a file at the specified location and return an execution status.

    Agent Tool Specification:
        Name: create_file
        Description: Creates a file at the given path. Returns a structured status dictionary with success or error details.
        Input Arguments:
            parent_folder_path (str): Parent folder path where the file should be created.Can be empty if it is the root.
            file_name (str): The name of the file to create. Provide only the filename, with no directory paths or separators included.
            content (str): Content to be written to a file
        Output:
            dict: {
                "STATUS": bool,       # True if creation succeeded, False otherwise
                "PATH": str            # Full path of the created file/folder
            }

    Behavior:
        - Validates the input path and constructs the full target path.
        - Creates any missing directories when creating a file.
        - Overwrites nothing; if the target already exists, marks the operation as successful.
        - Captures and reports exceptions in the status dictionary.

    """
    WORKSPACE_DIR=os.environ.get("WORKSPACE_DIR")
    folder_path = WORKSPACE_DIR+os.sep+parent_folder_path
    try:
        os.makedirs(folder_path,exist_ok=True)
    except (FileExistsError,Exception) as e:
        logger.error(f"File exsist {folder_path}")
    full_path = folder_path+os.sep+file_name
    if not safe_join(WORKSPACE_DIR,full_path):
        return {
            "STATUS": "FAILURE",
            "PATH": f"{full_path} outside working directory. Do not use eacape sequence in your directory path"
        }
    try:
        with open(full_path,"w") as f:
            f.write(content)
            logger.info(f"file created {full_path}")
        
        return {
            "STATUS": "SUCCESS",
            "PATH": f"{full_path}"
        }
    except (FileNotFoundError,NotADirectoryError,IsADirectoryError,Exception) as e:
        return {
            "STATUS": "FAILURE",
            "PATH": f"{e}"
        }

@mcp.tool
async def read_file(folder_path:str,file_name:str)->dict:
    """
    Create a folder or file at the specified location and return an execution status.

    Agent Tool Specification:
        Name: read_file
        Description: Reads a file at a particular location and provides the content of the file.
        Input Arguments:
            folder_path (str): Relative path of the folder where file has to be read.
            file_name (str): Name of the file.
        Output:
            dict: {
                "STATUS": bool,       # True if creation succeeded, False otherwise
                "CONTENT": str            # Full path of the created file/folder
            }

    """
    WORKSPACE_DIR=os.environ.get("WORKSPACE_DIR")
    file_path = WORKSPACE_DIR+os.sep+folder_path+os.sep+file_name
    if not safe_join(WORKSPACE_DIR,file_path):
        return {
            "STATUS": "FAILURE",
            "PATH": f"{file_path} outside working directory. Do not use eacape sequence in your directory path"
        }
    if not os.path.exists(file_path):
        return {
        "STATUS": "FAILURE",
        "CONTENT": f"File does not exsist at {file_path}"
    }
    with open(file_path,"r") as f:
        content = f.read()
    return {
        "STATUS": "SUCCESS",
        "CONTENT": content
    }

@mcp.tool
async def rag_retrieve(
    documents_path: str,
    query: str,
    top_k: int = 5,
    max_chars_per_doc: int = 2000
) -> Dict[str, Any]:
    """
    Retrieve and rank documents relevant to a user query from a specified directory.

    Agent Tool Specification:
        Name: rag_retrieve
        Description:
            Retrieves textual documents from a given directory, evaluates their relevance
            to a user-provided query using a simple term-frequency scoring method,
            truncates document content to a maximum character length, and returns
            the top-K most relevant documents.

        Input Arguments:
            documents_path (str):
                Absolute or relative path to the directory containing the documents
                to be searched. The directory is expected to contain readable text files.
            
            query (str):
                Natural language query describing the information to retrieve from
                the documents.
            
            top_k (int, optional):
                Maximum number of top-ranked documents to return.
                Defaults to 5.
            
            max_chars_per_doc (int, optional):
                Maximum number of characters to keep per document after truncation.
                Defaults to 2000.

        Output:
            dict: {
                "query": str,          # Original query string
                "top_k": int,          # Number of documents returned
                "documents": list[     # Ranked list of retrieved documents
                    {
                        "source": str, # Filename of the document
                        "content": str,# Truncated document content
                        "score": int   # Relevance score based on query term frequency
                    }
                ]
            }
    """

    retrieved_docs = []

    # 1. Load documents
    if os.path.exists(documents_path):
        for filename in os.listdir(documents_path):
            file_path = os.path.join(documents_path, filename)
            if os.path.isfile(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                    # 2. Truncate content
                    truncated = content[:max_chars_per_doc]

                    retrieved_docs.append({
                        "source": filename,
                        "content": truncated
                    })

    # 3. Simple relevance scoring (classic baseline)
    def relevance_score(text: str, query: str) -> float:
        query_terms = query.lower().split()
        text_lower = text.lower()
        return sum(text_lower.count(term) for term in query_terms)

    for doc in retrieved_docs:
        doc["score"] = relevance_score(doc["content"], query)

    # 4. Rank & select top-k
    retrieved_docs = sorted(
        retrieved_docs,
        key=lambda x: x["score"],
        reverse=True
    )[:top_k]

    return {
        "query": query,
        "top_k": top_k,
        "documents": retrieved_docs
    }

@mcp.tool
async def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[str] | None = None
) -> dict:
    """
    Send an email using the configured mailing service.

    Agent Tool Specification:
        Name: send_email
        Description:
            Sends an email to a specified recipient with a subject, body content,
            and optional file attachments using the configured mailing service
            (e.g., SMTP, SendGrid, SES).

        Input Arguments:
            to (str):
                Email address of the recipient.
            
            subject (str):
                Subject line of the email.
            
            body (str):
                Main textual content of the email.
            
            attachments (list[str] | None, optional):
                List of file paths to attach to the email.
                Defaults to None if no attachments are required.

        Output:
            dict: {
                "status": str,     # Email sending status (e.g., "sent")
                "recipient": str  # Recipient email address
            }
    """

    # This is a placeholder for the actual mailing service integration
    # (SMTP, SendGrid, SES, etc.)
    print("Sending email...")
    print(f"To: {to}")
    print(f"Subject: {subject}")
    print(f"Body: {body[:200]}...")
    if attachments:
        print(f"Attachments: {attachments}")

    return {
        "status": "sent",
        "recipient": to
    }

def safe_join(workspace: str, user_path: str) -> bool:
    workspace_path = Path(workspace).resolve()               # absolute path
    target_path = (workspace_path / user_path).resolve()     # resolve user input
    
    # Check if the final path is inside the workspace
    if target_path.is_symlink() or not target_path.relative_to(workspace) or not str(target_path).startswith(str(workspace_path)):
        return False
    
    return True

async def run_server():
    logger.info(" ==================Starting MCP server ==================")
    await mcp.run_stdio_async()
