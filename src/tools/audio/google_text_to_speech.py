# flake8: noqa: E501
from dotenv import load_dotenv
from google.cloud import texttospeech

load_dotenv()


def ssml_to_audio(ssml_text: str, output_file: str) -> None:
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US", name="en-US-Studio-O"
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    with open(output_file, "ab") as out:
        out.write(response.audio_content)
        print(f"Audio content appended to file {output_file}")


if __name__ == "__main__":
    output_file = "output_google.mp3"
    open(output_file, "wb").close()

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
