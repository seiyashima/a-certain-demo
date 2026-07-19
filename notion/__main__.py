from dotenv import load_dotenv

from .actions.publish_design import main


if __name__ == "__main__":
    # Load local .env so NOTION_* vars are available for CLI runs.
    load_dotenv()
    main()
