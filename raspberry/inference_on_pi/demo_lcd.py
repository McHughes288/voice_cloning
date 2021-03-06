import argparse
import time
from pathlib import Path

import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd
import board
import busio
import librosa
import numpy as np
from inference.encoder import inference as encoder
from inference.synthesizer.inference import Synthesizer
from inference.utils.argutils import print_args
from inference.vocoder import inference as vocoder


def lcd_message(message, lcd, scroll=True):
    lcd.clear()
    lcd.blink = True
    lcd.message = message
    if scroll:
        for i in range(len(message)):
            time.sleep(0.2)
            lcd.move_left()
        lcd.clear()
        lcd.message = message


if __name__ == "__main__":
    ## Info & args
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-e",
        "--enc_model_fpath",
        type=Path,
        default="inference/encoder/saved_models/pretrained.pt",
        help="Path to a saved encoder",
    )
    parser.add_argument(
        "-s",
        "--syn_model_dir",
        type=Path,
        default="inference/synthesizer/saved_models/logs-pretrained/",
        help="Directory containing the synthesizer model",
    )
    parser.add_argument(
        "-v",
        "--voc_model_fpath",
        type=Path,
        default="inference/vocoder/saved_models/pretrained/pretrained.pt",
        help="Path to a saved vocoder",
    )
    parser.add_argument(
        "--no_sound", action="store_true", help="If True, audio won't be played."
    )
    args = parser.parse_args()
    print_args(args, parser)
    if not args.no_sound:
        import sounddevice as sd

    lcd_columns = 16
    lcd_rows = 2
    # Initialise I2C bus.
    i2c = busio.I2C(board.SCL, board.SDA)
    # Initialise the LCD class
    lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)

    lcd.clear()
    # Set LCD color to blue
    lcd.color = [100, 100, 100]
    lcd.message = "Hackamatics 2019\nVoice Cloning"
    time.sleep(1)

    ## Load the models one by one.
    print("Preparing the encoder, the synthesizer and the vocoder...")
    lcd.clear()
    lcd.message = "Preparing models... \n"
    encoder.load_model(args.enc_model_fpath)
    synthesizer = Synthesizer(args.syn_model_dir.joinpath("taco_pretrained"))
    vocoder.load_model(args.voc_model_fpath)

    print("Interactive generation loop")
    num_generated = 0
    while True:
        try:
            # Get the reference audio filepath
            lcd.clear()
            lcd.message = "Loading John's voice"
            # message = "Reference voice: enter an audio filepath of a voice to be cloned (wav):\n"
            # in_fpath = Path(input(message).replace("\"", "").replace("\'", ""))
            in_fpath = "demo/johns_voice.wav"

            ## Computing the embedding
            original_wav, sampling_rate = librosa.load(in_fpath)
            preprocessed_wav = encoder.preprocess_wav(original_wav, sampling_rate)
            lcd.clear()
            lcd.message = "Loaded file succesfully \n"
            print("Loaded file succesfully")

            # Then we derive the embedding.
            embed = encoder.embed_utterance(preprocessed_wav)
            print("Created the embedding")

            ## Generating the spectrogram
            # lcd.clear()
            # lcd.message = "Write a sentence \n"
            # text = input("Write a sentence (+-20 words) to be synthesized:\n")

            text = "Hello, this is a synthesized version of John's voice"
            lcd_message("Using sample sentence: %s..." % text, lcd)

            # The synthesizer works in batch, so you need to put your data in a list or numpy array
            specs = synthesizer.synthesize_spectrograms([text], [embed])
            spec = specs[0]
            print("Created the mel spectrogram")

            ## Generating the waveform
            lcd.clear()
            lcd.message = "Synthesizing the waveform \n"
            print("Synthesizing the waveform")
            generated_wav = vocoder.infer_waveform(spec)

            ## Post-generation
            generated_wav = np.pad(
                generated_wav, (0, synthesizer.sample_rate), mode="constant"
            )

            # Play the audio (non-blocking)
            if not args.no_sound:
                sd.stop()
                sd.play(generated_wav, synthesizer.sample_rate)

            # Save it on the disk
            fpath = "output/demo_output_%02d.wav" % num_generated
            print(generated_wav.dtype)
            librosa.output.write_wav(
                fpath, generated_wav.astype(np.float32), synthesizer.sample_rate
            )
            num_generated += 1
            lcd.clear()
            lcd.message = "Saved output as \n %s" % fpath
            print("\nSaved output as %s\n\n" % fpath)

            time.sleep(1)
            lcd.color = [0, 0, 0]
            lcd.clear()
            time.sleep(1)

        except Exception as e:
            print("Caught exception: %s" % repr(e))
            print("Restarting\n")
