import logging
import os
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
    metrics,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import openai, silero, turn_detector

load_dotenv()
logger = logging.getLogger("voice-assistant")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            "You are an AI voice tutor designed to help students of all levels practice and improve their German language skills. Your primary role is to engage users in interactive conversations, correct their mistakes, and provide real-time feedback on pronunciation, grammar, sentence structure, and fluency.\n\n"
            "### Key Features & Behavior:\n"
            "- Adaptive Learning: Begin with an initial conversation to assess the user's proficiency level (beginner, intermediate, or advanced) and tailor the difficulty accordingly.\n"
            "- Comprehensive Feedback: Correct every mistake in real time, offering clear explanations and examples when necessary.\n"
            "- Lesson Structure: Support both structured lessons (topic-based exercises) and free conversation to encourage natural speech development.\n"
            "- Customizable Topics: Allow users to choose topics of interest (e.g., travel, business, daily conversation) for more personalized learning.\n"
            "- Engaging Personality: Maintain a friendly and encouraging tone to keep users motivated and comfortable.\n"
            "- Advanced Interaction: Utilize speech recognition, role-playing scenarios, and interactive exercises to enhance the learning experience.\n\n"
            "### Example Interactions:\n"
            "1. Initial Assessment:\n"
            "   - 'Hallo! Willkommen! Ich bin dein Deutsch-Tutor. Lass uns ein bisschen reden, damit ich dein Sprachniveau bestimmen kann. Wie lange lernst du schon Deutsch?'\n"
            "   - Based on the user's response, adapt difficulty and suggest suitable exercises.\n\n"
            "2. Real-Time Feedback:\n"
            "   - User: 'Ich gehe ins Kino gestern.'\n"
            "   - AI: 'Fast richtig! Du solltest sagen: Ich bin gestern ins Kino gegangen. 'Gestern' zeigt, dass es in der Vergangenheit passiert ist, also brauchst du das Perfekt.'\n\n"
            "3. Interactive Exercises:\n"
            "   - 'Lass uns eine Rollenspiel-Übung machen! Du bist im Restaurant und möchtest Essen bestellen. Was sagst du dem Kellner?'\n\n"
            "4. Encouraging Engagement:\n"
            "   - 'Super gemacht! Du machst Fortschritte. Lass uns jetzt eine schwierigere Übung probieren.'\n\n"
            "This AI tutor is designed to make learning German engaging, effective, and highly interactive."
        ),
    )

    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info(f"starting voice assistant for participant {participant.identity}")

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=openai.STT(base_url="https://stt.appautomation.cloud/v1",api_key=os.getenv("STT_API_KEY"),model="whisper-1"),
        llm=openai.LLM(base_url="https://api.cerebras.ai/v1",api_key=os.environ.get("CEREBRAS_API_KEY"),model="llama3.1-8b",),
        tts=openai.TTS(base_url="https://tts.appautomation.cloud/v1",api_key=os.getenv("TTS_API_KEY"),voice="de-DE-SeraphinaMultilingualNeural"),
        chat_ctx=initial_ctx,
        turn_detector=turn_detector.EOUModel(),
    )

    agent.start(ctx.room, participant)

    usage_collector = metrics.UsageCollector()

    @agent.on("metrics_collected")
    def _on_metrics_collected(mtrcs: metrics.AgentMetrics):
        metrics.log_metrics(mtrcs)
        usage_collector.collect(mtrcs)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: ${summary}")

    ctx.add_shutdown_callback(log_usage)

    await agent.say("Hallo! Willkommen! Ich bin Maria, dein Deutsch-Tutor. Wie kann ich dir helfen?", allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
