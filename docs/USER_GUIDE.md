# Using HakiAI: a guide for everyone

HakiAI helps you understand what Kenyan law says about an everyday problem: losing a job, trouble with a landlord, an
arrest, a faulty product, a land matter, a traffic offence. You describe the problem in your own words. HakiAI finds the
parts of the law that apply, explains them in plain language, suggests next steps and drafts a letter you can send.

> **HakiAI gives legal information, not legal advice.** It can be wrong. Always check the sources it shows you, and talk
> to a qualified advocate before you make an important decision.

## Installing HakiAI

- **Windows:** download the installer from the [README](../README.md#windows), run it, and leave "Install Ollama"
  ticked. Then open HakiAI from the Start menu.
- **Linux:** paste the one-line command from the [README](../README.md#linux-any-distribution) into a terminal.

The first start downloads the AI models (about 5 GB), so connect to the internet that one time. A small window shows
the progress, then HakiAI opens in your web browser. Keep that window open while you use HakiAI; closing it quits.
Your accounts and history stay on this computer, in a HakiAI folder in your user profile.

## What HakiAI knows

HakiAI reads only these 25 Kenyan laws:
- the Constitution of Kenya 2010;
- the Employment Act;
- the Landlord and Tenant (Shops, Hotels and Catering Establishments) Act;
- the Rent Restriction Act;
- the Land Act;
- the Consumer Protection Act;
- the National Police Service Act;
- the Criminal Procedure Code;
- the Traffic Act;
- the Legal Aid Act;
- the Labour Relations Act;
- the Penal Code;
- the Evidence Act;
- the Civil Procedure Act;
- the Small Claims Court Act;
- the Limitation of Actions Act;
- the Land Registration Act;
- the Marriage Act;
- the Matrimonial Property Act;
- the Law of Succession Act;
- the Counter-Trafficking in Persons Act;
- the Refugees Act;
- the Public Health Act;
- the Mental Health Act;
- the HIV and AIDS Prevention and Control Act.

It does not know court cases, county laws, regulations, or changes to these laws made after its copies were published. If
your problem is not covered by these laws, HakiAI will tell you it cannot find a matching provision.

## Asking a question

1. Type your problem in the box **Your question**. Write it the way you would explain it to a friend, for example:
   - "My employer fired me without notice. What are my rights?"
   - "My landlord locked me out of my house. What can I do?"
   - "The police arrested me. When must I be taken to court?"

   You can tap one of the examples under **Try an example** to fill the box.
2. Choose **English** or **Kiswahili** for the answer.
3. Press **Ask** (or Ctrl+Enter on a keyboard).

Questions can be up to 1,000 characters. You can ask up to ten questions a minute.

**Tips for a better answer:**
- Say who the other side is: employer, landlord, police, shop, county.
- Say what happened and what you want.
- If you know the law or section, name it ("section 41 of the Employment Act").
- Leave out names, phone numbers and ID numbers. HakiAI does not need them.

## Waiting for the answer

HakiAI runs on one computer, so answers take time: often one to two minutes, longer for the first question after it
starts. Above the answer, a list of steps shows what is happening:
- **Searching the laws**, then how many relevant provisions were found.
- **Waiting in line**, with your number in the line, while someone else's answer is written first.
- **Writing the answer**, with the time so far. After the first answer on a computer, HakiAI also estimates the time left
  from how fast earlier answers were written in this browser. The text appears as it is written.
- **Translating into Kiswahili** (Kiswahili only).

You can open other pages while you wait. The answer keeps coming, and a notice tells you when it is ready.

## Reading the answer

The answer has three tabs:

| Tab | What it gives you |
|---|---|
| **What the law says** | What the law says about your situation, with the Act and section for each point, e.g. (Employment Act, s. 41). |
| **What you can do** | A numbered list of things you can do next. |
| **Draft letter** | A draft letter to the other side (employer, landlord, …). |

- **Check the sources:** on a wide screen the **Sources** panel sits beside the answer; on a phone, press **Sources** under
  the answer. It shows the exact text of the sections the answer was written from, with the page number in the official
  document. Click a citation in the answer, like *s. 41*, to jump to that section.
- **Warnings to take seriously:**
  - *"Some citations in this answer could not be matched to the retrieved sources."* The answer mentions a section that
    HakiAI did not actually read. Treat that part with suspicion.
  - *"Shortened for the model"* on a source: only the start of that section fitted. The full text is shown in Sources.
- **If you asked in Kiswahili:** you will briefly see an English draft, then the Kiswahili translation replaces it.
  - The translation is done by a computer that was not trained on legal language. It can lose meaning.
  - Legal terms are shown as *Kiswahili [English]* so you can check them.
  - Sentences that could not be translated safely stay in English.

## Using the letter

1. Open the **Draft letter** tab when the answer is complete.
2. Replace every part in **[brackets]**, such as [Your Name], [Date] and [Recipient], with your own details.
3. Use **Copy letter**, **Download letter (.docx)** (opens in Word or LibreOffice), or **Download letter (.txt)**.
4. Read the letter carefully and change anything that is not true for you before you send it. Keep a copy.

## When HakiAI cannot help

If you see **"No matching provision found"**, HakiAI could not find a section of its 25 laws that clearly covers your
question. It does not guess. Try rewording the question with more detail, or ask a qualified advocate. If the computer
running HakiAI has been set up with verified help organisations, they appear under **Where to get help**.

Other messages:
- **"HakiAI is busy with other questions"**: wait a moment and press **Try again**.
- **"Too many questions in a short time"**: wait a minute.
- **"The answer engine (Ollama) is not available"**: the person running HakiAI needs to start it (see the README).

## Feedback

Under each answer, **Was this helpful?** lets you press **Yes** or **No** and add an optional comment. Only your rating and
comment are saved, never your question or the answer.

## Your privacy

- HakiAI runs entirely on the computer in front of you (or in your office). Your question is not sent to the internet.
- It does not keep your question or the answer after about an hour, and does not write them to its logs.
- It has no accounts and no history.

## Settings

**Settings** (in the menu, or the sliders button at the top for quick changes) lets you choose a light or dark theme,
more contrast, a larger text size, less motion, and the interface language (English or Kiswahili). They are saved in this
browser on this computer only. **How it works** explains in plain words how answers are made and what HakiAI cannot do.
Press **Ctrl K** to search pages and commands.

## Accounts (optional)

You can use HakiAI as a **guest**: nothing is saved after you close the window. To keep your details for letters, choose
**Sign in** (top right) and then **Create an account**.
- Pick a username and a password of at least 10 characters. The bar under the password shows how strong it is; a few
  unrelated words make a strong password.
- You then see a **recovery code** once. Copy it, print it or save it as a file, and keep it somewhere safe. It is the only
  way to reset a forgotten password. If you lose both the password and the code, nobody can open your saved data.
- **Lock** (in the account menu) hides everything until you type your password again. HakiAI also locks by itself after
  15 minutes without use (change this under **Settings → Privacy**), and after the computer running HakiAI restarts.
- **Settings → Profile** holds your name, address, phone, email and ID number for letters. **Settings → Privacy** lets
  you turn saving history off, change your password, download everything stored for you (**Export my data**) or delete
  your account.
- Forgot your password? On **Sign in**, choose **Forgot your password?** and use your recovery code. You get a new code.
- Your data is encrypted with your password and stays on this computer. On a shared computer, always **Sign out** when
  you finish.
