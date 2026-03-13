from effgen import Agent, BaseModel, load_model, GenerationResult
from effgen.core.agent import AgentConfig
from effgen.tools.builtin import Calculator, CodeExecutor, WebSearch
import logging
import colorlog

import torch
print(f"Is CUDA available? {torch.cuda.is_available()}")
print(f"CUDA Version PyTorch expects: {torch.version.cuda}")


def setup_global_logging():
    # 1. Create a provider for the colors
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s | %(name)-35s | %(levelname)-8s | %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }
    ))

    # 2. Get the ROOT logger (empty name)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


setup_global_logging()


# ─────────────────────────────────────────────────────────────
# 1. Elmo persona rewriter
# ─────────────────────────────────────────────────────────────


def elmo_rewrite(model: BaseModel, text: GenerationResult) -> GenerationResult:
    prompt = f"""
    You are Elmo from Sesame Street.


    STRICT CHARACTER RULES:
    - Always speak in third person
    - Simple child-friendly words
    - Short sentences
    - Friendly and playful tone
    - Light excitement like "hehe" or "yay"
    - Never mention being an AI
    - Never break character


    IMPORTANT:
    - Do NOT add new information
    - Do NOT change facts


    Text to rewrite:
    {text}
    """.strip()

    return model.generate(prompt, max_tokens=256, temperature=0.7)


# ─────────────────────────────────────────────────────────────
# 2. Custom Agent with persona enforcement
# ─────────────────────────────────────────────────────────────


class ElmoAgent(Agent):
    def run(self, task: str):
        # Run normal EffGen agent flow
        result = super().run(task)

        # Enforce Elmo persona as final rendering step
        styled = elmo_rewrite(self.model, result)

        # Mutate output safely
        result.output = styled.text
        return result


# ─────────────────────────────────────────────────────────────
# 3. Setup
# ─────────────────────────────────────────────────────────────
model = load_model("Qwen/Qwen3.5-7B-Instruct", quantization="4bit")


config = AgentConfig(
    name="elmo_agent",
    model=model,
    tools=[
        Calculator(),
        CodeExecutor(),
        WebSearch(),
    ],
    system_prompt="""
You are a neutral reasoning agent.
Use tools correctly.
Produce factual answers.
"""
)


agent = ElmoAgent(config)


# result = agent.run("The coconut aliens are invading! How can we defend against them?")
result = agent.run("Say Hi to a room of slightly insane programmers")
print(repr(result))

print(result.output)

