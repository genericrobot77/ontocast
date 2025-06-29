"""Test API client for OntoCast.

This module provides a simple command-line client for testing the OntoCast API.
It can send requests to the API server with either a default payload or
a custom JSON payload from a file.

The client supports:
- Custom server URLs
- JSON payload loading from files
- Default test payload for Apple 10-Q document
- Response formatting and display

Example:
    python test_api.py --url http://localhost:8999
    python test_api.py --url http://localhost:8999 --json-file payload.json
"""

import json

import click
import requests


@click.command()
@click.option("--url", help="Base URL for the server (e.g. http://localhost:8999")
@click.option(
    "--json-file",
    type=click.Path(exists=True),
    default=None,
    help="Path to JSON file to send as payload",
)
def main(url, json_file):
    """Send a test request to the OntoCast API server.

    This function sends a POST request to the specified API endpoint with
    either a custom JSON payload from a file or a default test payload
    containing Apple's 10-Q document text.

    Args:
        url: The base URL of the API server to send the request to.
        json_file: Optional path to a JSON file containing the request payload.

    Example:
        >>> main("http://localhost:8999", None)
        # Sends default Apple 10-Q payload

        >>> main("http://localhost:8999", "custom_payload.json")
        # Sends custom payload from file
    """
    if json_file:
        with open(json_file, "r") as f:
            payload = json.load(f)
    else:
        payload = {
            "text": (
                "## UNITED STATES SECURITIES AND EXCHANGE COMMISSION\n\nWashington, D.C. 20549 ## FORM 10-Q\n\n<!-- image -->\n\n(Mark One)\n\n\u2612 QUARTERLY REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934\n\nFor the quarterly period ended April 1, 2023\n\nor\n\n\u2610 TRANSITION REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934\n\nFor the transition period from              to             .\n\nCommission File Number: 001-36743 ## Apple Inc.\n\n(Exact name of Registrant as specified in its charter)\n\nCalifornia\n\n94-2404110\n\n(State or other jurisdiction of incorporation or organization)\n\n(I.R.S. Employer Identification No.)\n\nOne Apple Park Way Cupertino, California\n\n95014\n\n(Address of principal executive offices)\n\n(Zip Code) ## (408) 996-1010\n\n(Registrant's telephone number, including area code)\n\nSecurities registered pursuant to Section 12(b) of the Act:\n\nTitle of each class\n\nTrading symbol(s)\n\nName of each exchange on which registered\n\nCommon Stock, $0.00001 par value per share\n\nAAPL\n\nThe Nasdaq Stock Market LLC\n\n1.375% Notes due 2024\n\n-\n\nThe Nasdaq Stock Market LLC\n\n0.000% Notes due 2025\n\n-\n\nThe Nasdaq Stock Market LLC\n\n0.875% Notes due 2025\n\n-\n\nThe Nasdaq Stock Market LLC\n\n1.625% Notes due 2026\n\n-\n\nThe Nasdaq Stock Market LLC\n\n2.000% Notes due 2027\n\n-\n\nThe Nasdaq Stock Market LLC\n\n1.375% Notes due 2029\n\n-\n\nThe Nasdaq Stock Market LLC\n\n3.050% Notes due 2029\n\n-\n\nThe Nasdaq Stock Market LLC\n\n0.500% Notes due 2031\n\n-\n\nThe Nasdaq Stock Market LLC\n\n3.600% Notes due 2042\n\n-\n\nThe Nasdaq Stock Market LLC\n\nIndicate by check mark whether the Registrant (1) has filed all reports required to be filed by Section 13 or 15(d) of the Securities Exchange Act of 1934 during the preceding 12 months (or for such shorter period that the Registrant was required to file such reports), and (2) has been subject to such filing requirements for the past 90 days.\n\nYes \u2612\n\nNo \u2610\n\nIndicate by check mark whether the Registrant has submitted electronically every Interactive Data File required to be submitted pursuant to Rule 405 of Regulation S-T (\u00a7232.405 of this chapter) during the preceding 12 months (or for such shorter period that the Registrant was required to submit such files).\n\nYes \u2612\n\nNo \u2610\n\nIndicate by check mark whether the Registrant is a large accelerated filer, an accelerated filer, a non-accelerated filer, a smaller reporting company, or an emerging growth company. See the definitions of 'large accelerated filer,' 'accelerated filer,' 'smaller reporting company,' and 'emerging growth company' in Rule 12b-2 of the Exchange Act.\n\nLarge accelerated filer\n\n\u2612\n\nAccelerated filer\n\n\u2610\n\nNon-accelerated filer\n\n\u2610\n\nSmaller reporting company\n\n\u2610\n\n\u2610\n\nEmerging growth company\n\nIf  an  emerging growth company, indicate by check mark if the Registrant has elected not to use the extended transition period for complying with any new or revised financial accounting standards provided pursuant to Section 13(a) of the Exchange Act. \u2610\n\nIndicate by check mark whether the Registrant is a shell company (as defined in Rule 12b-2 of the Exchange Act).\n\nYes \u2610\n\nNo \u2612\n\n15,728,702,000 shares of common stock were issued and outstanding as of April 21, 2023. ## Apple Inc. ## Form 10-Q ## For the Fiscal Quarter Ended April 1, 2023"
            ),
        }

    print(f"POSTing to: {url}")
    r = requests.post(url, json=payload)
    print(f"Status: {r.status_code}")
    print("Response:")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)


if __name__ == "__main__":
    main()
