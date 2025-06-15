import click
import requests

jf = {
    "text": (
        "Since the discovery of tumour initiating cells (TICs) in solid"
        " tumours, studies focussing on their role in cancer initiation and"
        " progression have abounded. The biological interrogation of these"
        " cells continues to yield volumes of information on their"
        " pro-tumourigenic behaviour, but actionable generalised conclusions"
        " have been scarce."
    ),
}


@click.command()
@click.option("--url", type=click.STRING, default=None)
def main(url):
    r = requests.post(url, json=jf)
    print(r)


if __name__ == "__main__":
    main()
