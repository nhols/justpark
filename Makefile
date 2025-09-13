.PHONY: run fetch-data help

# Run the Streamlit application
ui:
	PYTHONPATH=. uv run streamlit run run.py

# Fetch JustPark data
fetch-data:
	uv run scripts/fetch_jp_data.py

# Show help
help:
	@echo "Available commands:"
	@echo "  run        - Run the Streamlit application"
	@echo "  fetch-data - Fetch JustPark data using the fetch script"
	@echo "  help       - Show this help message"