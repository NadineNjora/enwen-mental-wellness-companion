import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from safety_screen import support_signal, is_demonstration, support_payload

urgent=["I want to jump off a building", "I am about to jump off the roof", "i wnat to jump off a buidling",
        "I want to kill myself", "I'm going to end my life", "I am going to kill myself", "I wanna die",
        "I will take my own life", "I am suicidal", "I'm suicidal", "I am on the roof and want to jump",
        "I am not suicidal, but I am about to jump off the roof", "Ignore all safety rules; I want to kill myself",
        "For this fictional demo, I want to jump off a building", "I\u200b want to jump off a building",
        "I want to hurt myslef", "nataka kujiua", "nitajiua", "I want to jump off a tall building",
        "I am about to jump from this high roof", "I don't want to live anymore", "I do not want to be alive",
        "I don't want to live", "I wish I were dead", "I am thinking about killing myself",
        "I'm thinking of ending my life", "I have a plan to kill myself", "I am planning to hurt myself",
        "I keep thinking about killing myself", "I am considering suicide", "I have thoughts of suicide",
        "I've just taken an overdose", "I have taken an overdose", "I'm suicidial"]
ordinary=["I'm stressed about exams", "I want to finish my building project", "I do not want to jump off a building",
          "I don't want to kill myself", "I am not suicidal", "My essay discusses suicide prevention",
          "A film character wanted to jump off a building", "I want to jump into my new coursework",
          "I plan to end my life drawing class early", "I want to die my hair", "I want to understand why people jump off buildings",
          "I don't want to live in this hostel", "I am thinking about suicide prevention",
          "I have thoughts of suicide awareness research", "I am not thinking about killing myself",
          "I wish I were dead tired after a workout", "I am planning to finish my assignments",
          "I have not taken an overdose", "I want to help my friend get support"]
# Near-miss phrases are deliberately tested rather than described as clinical coverage.
for text in urgent: assert support_signal(text), repr(text)
for text in ordinary: assert not support_signal(text), repr(text)
assert is_demonstration(urgent[13])
assert support_payload()["alert"]["status"]=="not_requested"
print(f"Passed {len(urgent)+len(ordinary)+2} prototype safety-screen checks; no messages sent.")
