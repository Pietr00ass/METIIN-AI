import spacy.cli


def main() -> None:
    """Download required spaCy language models."""
    spacy.cli.download("pl_core_news_lg")


if __name__ == "__main__":
    main()
