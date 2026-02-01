# flake8: noqa: E501
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def ssml_to_audio(ssml_text: str, output_file: str) -> None:
    """
    Generates audio from SSML text using OpenAI's Text-to-Speech API.

    Args:
        ssml_text: string of SSML text
        output_file: name of the output audio file
    """

    client = OpenAI()

    response = client.audio.speech.create(
        model="tts-1", voice="alloy", input=ssml_text
    )

    with open(output_file, "ab") as out:
        out.write(response.content)
        print(f"Audio content appended to file {output_file}")


if __name__ == "__main__":
    output_file = "output_openai.mp3"
    Path(output_file).write_bytes(b"")

    text_parts = [
        """<speak>
        <prosody rate="0.90">Find a comfortable seated position, allowing your body to feel relaxed yet alert.</prosody>
        <break time="1500ms"/>
        <prosody rate="0.80">Close your eyes gently, and take a deep breath in... and out.</prosody>
        <break time="2000ms"/>
        <prosody rate="0.90">As you settle into this moment, begin to notice any sensations in your body.</prosody>
        <break time="1000ms"/>
        <prosody rate="0.80">Bring your awareness to your breath, feeling the rise and fall of your chest with each inhale and exhale.</prosody>
        <break time="2000ms"/>
        </speak>""",
        """<speak>
        <prosody rate="0.70">If you notice thoughts of stress beginning to surface, acknowledge them without judgment.</prosody>
        <break time="2000ms"/>
        <prosody rate="0.80">Simply recognize these thoughts as they come, and allow them to pass like clouds in the sky.</prosody>
        <break time="2000ms"/>
        <prosody rate="0.90">Bring your focus back to your breath, feeling each inhalation nourishing you, and each exhalation releasing tension.</prosody>
        <break time="2000ms"/>
        </speak>""",
        """<speak>
        <prosody rate="0.80">Embrace the present moment, free from the weight of the past or the worry of the future.</prosody>
        <break time="2000ms"/>
        <prosody rate="0.70">With each breath, let go of the stress that does not serve you, creating space for calm and clarity.</prosody>
        <break time="2000ms"/>
        <prosody rate="1.10">Continue to breathe... in... and out...</prosody>
        <break time="1000ms"/>
        </speak>""",
        """<speak>
        <prosody rate="0.80">Allow yourself to simply be here, in this moment, without needing to change anything.</prosody>
        <break time="2000ms"/>
        <prosody rate="0.90">When you are ready, gently bring your awareness back to the room, and open your eyes.</prosody>
        <break time="1500ms"/>
        <prosody rate="0.90">Carry this sense of mindfulness with you as you move through your day.</prosody>
        <break time="2000ms"/>
        </speak>""",
    ]

    for i, part in enumerate(text_parts):
        ssml_to_audio(part, output_file)
        print(f"Processed part {i + 1}/{len(text_parts)}")

    print(f"All audio content written to file '{output_file}'")
