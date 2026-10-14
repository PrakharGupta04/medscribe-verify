import os

vbs = '''
Set voice = CreateObject("SAPI.SpVoice")
Set stream = CreateObject("SAPI.SpFileStream")
stream.Open "test_en.wav", 3, False
Set voice.AudioOutputStream = stream
voice.Speak "I am not taking any medications."
stream.Close
'''
with open("gen_en.vbs", "w", encoding="utf-8") as f:
    f.write(vbs)

os.system("cscript //nologo gen_en.vbs")
if os.path.exists("test_en.wav"):
    print("test_en.wav generated successfully! Size:", os.path.getsize("test_en.wav"))
else:
    print("Failed to generate test_en.wav")
