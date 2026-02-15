"""Test Azure Speech Service transcription with audio file."""

import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to path to import from backend package
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    print("Error: azure-cognitiveservices-speech not installed")
    print("Install with: pip install azure-cognitiveservices-speech")
    sys.exit(1)


def convert_to_wav(input_file: Path, output_file: Path) -> bool:
    """
    Convert audio file to WAV format using ffmpeg.
    
    Args:
        input_file: Path to input audio file
        output_file: Path to output WAV file
        
    Returns:
        True if conversion succeeded, False otherwise
    """
    try:
        # Check if ffmpeg is available
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        if result.returncode != 0:
            return False
        
        print(f"Converting {input_file.name} to WAV format...")
        
        # Convert to 16kHz mono WAV (optimal for speech recognition)
        result = subprocess.run(
            [
                "ffmpeg",
                "-i", str(input_file),
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",       # Mono
                "-acodec", "pcm_s16le",  # 16-bit PCM
                str(output_file),
                "-y"  # Overwrite output file
            ],
            capture_output=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"✓ Conversion successful: {output_file.name}")
            return True
        else:
            print(f"✗ Conversion failed: {result.stderr.decode()}")
            return False
            
    except FileNotFoundError:
        print("ffmpeg not found. Install with: brew install ffmpeg")
        return False
    except subprocess.TimeoutExpired:
        print("Conversion timed out")
        return False
    except Exception as e:
        print(f"Conversion error: {e}")
        return False


def transcribe_audio_file(audio_path: str) -> str:
    """
    Transcribe an audio file using Azure Speech Service.
    
    Args:
        audio_path: Path to the audio file to transcribe
        
    Returns:
        The transcribed text
        
    Raises:
        RuntimeError: If transcription fails
    """
    # Get Azure Speech credentials from environment
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")
    
    if not speech_key or not speech_region:
        raise RuntimeError(
            "Missing Azure Speech credentials. "
            "Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in .env file"
        )
    
    print(f"Using Azure Speech region: {speech_region}")
    print(f"Transcribing: {audio_path}")
    print("-" * 60)
    
    # Configure Azure Speech
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region
    )
    
    # Set recognition language to English (US)
    speech_config.speech_recognition_language = "en-US"
    
    # Use push stream for better compatibility with various audio formats
    # This approach works with M4A and other compressed formats
    try:
        # Try to read the audio file
        with open(audio_path, 'rb') as audio_file:
            audio_data = audio_file.read()
        
        print(f"Audio file size: {len(audio_data)} bytes")
        
        # Create push stream
        push_stream = speechsdk.audio.PushAudioInputStream()
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        
        # Create speech recognizer
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        
        # For continuous recognition to handle longer audio
        all_results = []
        done = False
        
        def stop_cb(evt):
            """Callback to stop continuous recognition."""
            nonlocal done
            done = True
        
        def recognized_cb(evt):
            """Callback for recognized speech."""
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                all_results.append(evt.result.text)
        
        # Connect callbacks
        recognizer.recognized.connect(recognized_cb)
        recognizer.session_stopped.connect(stop_cb)
        recognizer.canceled.connect(stop_cb)
        
        # Start continuous recognition
        print("Starting transcription...")
        recognizer.start_continuous_recognition()
        
        # Push audio data
        push_stream.write(audio_data)
        push_stream.close()
        
        # Wait for completion (with timeout)
        import time
        timeout = 60  # 60 seconds timeout
        start_time = time.time()
        while not done and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        # Stop recognition
        recognizer.stop_continuous_recognition()
        
        if not all_results:
            raise RuntimeError("No speech could be recognized in the audio file")
        
        print(f"✓ Transcription successful! ({len(all_results)} segments)")
        return " ".join(all_results)
        
    except FileNotFoundError:
        raise RuntimeError(f"Audio file not found: {audio_path}")
    except Exception as e:
        raise RuntimeError(f"Error during transcription: {str(e)}")


def main():
    """Main test function."""
    # Path to test audio file (in project root)
    project_root = Path(__file__).parent.parent
    audio_file_m4a = project_root / "test_handoff.m4a"
    audio_file_wav = project_root / "test_handoff.wav"
    
    # Determine which audio file to use
    audio_file = None
    
    if audio_file_wav.exists():
        audio_file = audio_file_wav
        print("✓ Found WAV audio file")
    elif audio_file_m4a.exists():
        print("✓ Found M4A audio file")
        # Try to convert to WAV
        if convert_to_wav(audio_file_m4a, audio_file_wav):
            audio_file = audio_file_wav
        else:
            print("⚠ Conversion failed, using M4A (may not work)")
            audio_file = audio_file_m4a
    else:
        print(f"✗ Error: No audio file found")
        print(f"Expected: {audio_file_wav} or {audio_file_m4a}")
        sys.exit(1)
    
    try:
        transcript = transcribe_audio_file(str(audio_file))
        
        print("\n" + "=" * 60)
        print("TRANSCRIPT:")
        print("=" * 60)
        print(transcript)
        print("=" * 60)
        print(f"\nTranscript length: {len(transcript)} characters")
        
        # Test with intake agent extraction
        print("\n" + "=" * 60)
        print("TESTING EXTRACTION WITH INTAKE AGENT:")
        print("=" * 60)
        
        try:
            from backend.intake_agent import PatientIntakeAgent
            
            agent = PatientIntakeAgent()
            summary = agent.extract(transcript)
            
            print("\nExtracted Data:")
            print(f"  Confidence: {summary.confidence:.2f}")
            print(f"  Reasoning: {summary.reasoning}")
            print(f"  Patient: {summary.patient_name}")
            print(f"  Room: {summary.room_number}")
            print(f"  Age: {summary.age}")
            print(f"  Chief Complaint: {summary.chief_complaint}")
            print(f"  Medications: {summary.medications}")
            print(f"  Pending Tasks: {summary.pending_tasks}")
            print(f"  Vitals: {summary.vitals}")
            print(f"  Safety Alerts: {summary.safety_alerts}")
            
        except Exception as e:
            print(f"⚠ Could not test extraction: {e}")
        
    except RuntimeError as e:
        print(f"\n✗ Transcription failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
