const hasMatch = (text, pattern) => pattern.test(text);

const personalInformationPattern =
  /\b(?:social\s+security\s+(?:number|no\.?)|ssn|bank\s+(?:account|routing)|routing\s+number|credit\s+card\s+(?:number|details)|driver'?s?\s+license|passport\s+(?:number|copy)|date\s+of\s+birth|mother'?s\s+maiden\s+name)\b/i;

const informationRequestPattern =
  /\b(?:send|reply with|provide|share|submit|upload|give us|we need|need you to|asking for)\b/i;

const checks = [
  {
    name: "Personal email address",
    test: (text) =>
      hasMatch(
        text,
        /\b[\w.+-]+@(?:gmail|yahoo|hotmail|outlook|live|icloud|aol|proton(?:mail)?|mail)\.[a-z]{2,}\b/i,
      ),
    why: "A real employer usually uses its own company email domain. A free personal address makes it harder to confirm who is contacting you.",
    whatToDo: "Check the sender's domain against the employer's official website. Verify the recruiter before sharing documents.",
  },
  {
    name: "Interview only through a messaging app",
    test: (text) =>
      hasMatch(text, /\b(?:interview|screening)\b[^.!?\n]{0,80}\b(?:telegram|whatsapp)\b/i) ||
      hasMatch(text, /\b(?:telegram|whatsapp)\b[^.!?\n]{0,80}\b(?:interview|screening)\b/i),
    why: "A recruiter who keeps interviews only on Telegram or WhatsApp can avoid normal employer oversight and may be harder to verify.",
    whatToDo: "Ask for an interview through the employer's official careers site or verified company email. Look up the recruiter independently.",
  },
  {
    name: "Request for money, fees, or purchases",
    test: (text) =>
      hasMatch(
        text,
        /\b(?:pay|payment|send|transfer|deposit|purchase|buy|cover)\b[^.!?\n]{0,80}\b(?:fee|fees|training|application|background check|equipment|supplies|materials|registration|processing|gift\s*cards?|itunes\s*cards?|google\s*play\s*cards?|bitcoin|crypto(?:currency)?|ethereum|wire\s+transfer|money\s+transfer)\b|\b(?:gift\s*cards?|itunes\s*cards?|google\s*play\s*cards?|bitcoin|crypto(?:currency)?|ethereum)\b[^.!?\n]{0,80}\b(?:buy|purchase|send|transfer|pay|deposit)\b/i,
      ),
    why: "Legitimate employers do not charge candidates to apply or start work. Gift-card, crypto, and transfer requests can be difficult to reverse.",
    whatToDo: "Do not pay or buy anything. Verify the offer with the employer using contact details from its official website.",
  },
  {
    name: "Early request for personal or financial details",
    test: (text) =>
      hasMatch(text, informationRequestPattern) &&
      hasMatch(text, personalInformationPattern),
    why: "Identity and banking details can be used for fraud. A request before a verified offer is a serious warning sign.",
    whatToDo: "Do not send these details during an informal application or chat. Verify the employer and offer before using a secure payroll process.",
  },
  {
    name: "Unrealistic pay or effortless income",
    test: (text) =>
      hasMatch(
        text,
        /\b(?:guaranteed\s+(?:income|earnings|pay)|unlimited\s+(?:income|earnings)|get\s+rich\s+quick|easy\s+money|quick\s+money|risk[- ]free\s+income|earn\s+(?:up\s+to\s+)?\$\s?[\d,]+\s*(?:a|per|\/)\s*(?:day|week)\b[^.!?\n]{0,70}\b(?:easy|little work|no experience|from home))|\$\s?(?:[1-9]\d{2,})\s*(?:a|per|\/)\s*hour\b|\$\s?(?:[1-9]\d{2,})\s*(?:a|per|\/)\s*day\b|\$\s?(?:[3-9],?\d{3}|\d{2},?\d{3})\s*(?:a|per|\/)\s*week\b/i,
      ),
    why: "Promises of unusually high or guaranteed earnings for little work are used to make people act before checking whether a job is genuine.",
    whatToDo: "Compare the pay with similar roles and ask for the duties, pay structure, and employment terms in writing.",
  },
  {
    name: "Urgency or pressure",
    test: (text) =>
      hasMatch(
        text,
        /\b(?:act\s+now|apply\s+now[^.!?\n]{0,40}\b(?:today|immediately|limited)|urgent(?:ly)?|immediate(?:ly)?\s+(?:hire|hiring|start)|hired?\s+(?:immediately|today|on\s+the\s+spot)|today\s+only|limited\s+(?:spots|positions|time)|last\s+chance|don'?t\s+miss\s+out|start\s+(?:today|immediately))\b/i,
      ),
    why: "Pressure can leave little time to verify the employer and push you into sharing information or money quickly.",
    whatToDo: "Slow down. Ask for a normal interview and written offer, then confirm them through contact details you find yourself.",
  },
  {
    name: "Vague company or role",
    test: (text) =>
      hasMatch(
        text,
        /\b(?:company|employer)\s+(?:name|details|identity)\b[^.!?\n]{0,70}\b(?:confidential|not disclosed|provided later|after hiring)|\b(?:role|position|job|duties|responsibilities)\b[^.!?\n]{0,70}\b(?:not specified|not disclosed|discussed later|provided later|details later)\b|\b(?:no job description|no role details|duties will be shared later)\b/i,
      ),
    why: "A real opening should identify the employer and explain the work. Missing details make it harder to check whether the job exists.",
    whatToDo: "Ask for the company name, official website, job description, and duties before sharing personal details.",
  },
  {
    name: "Cheque or payment forwarding",
    test: (text) =>
      hasMatch(
        text,
        /\b(?:send|receive|deposit|cash)\b[^.!?\n]{0,70}\b(?:check|cheque)\b|\b(?:check|cheque)\b[^.!?\n]{0,70}\b(?:deposit|cash|forward|equipment|supplies)\b|\b(?:receive|process)\b[^.!?\n]{0,60}\b(?:payments|money|funds)\b[^.!?\n]{0,60}\b(?:forward|transfer|send)\b|\b(?:forward|transfer|send)\b[^.!?\n]{0,60}\b(?:payments|money|funds)\b[^.!?\n]{0,60}\b(?:for us|for the company|on our behalf)\b/i,
      ),
    why: "A fake cheque can later be reversed, and forwarding payments can make you responsible for stolen money.",
    whatToDo: "Do not deposit a cheque or move money for an employer. Contact your bank and verify the offer directly with the company.",
  },
  {
    name: "Poor grammar paired with a personal-information request",
    test: (text) =>
      hasMatch(text, /\b(?:we is|you is|for verify|need you send|i am recruiter of)\b/i) &&
      hasMatch(text, informationRequestPattern) &&
      hasMatch(text, personalInformationPattern),
    why: "Unusual grammar paired with a request for identity or financial details can indicate an impersonator collecting sensitive data.",
    whatToDo: "Do not reply with personal details. Check the employer's official website and contact its published recruiting address.",
  },
];

function checkJobPost(text) {
  const source = typeof text === "string" ? text : "";
  return checks
    .filter((check) => check.test(source))
    .map(({ name, why, whatToDo }) => ({ name, why, whatToDo }));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { checks, checkJobPost };
}

globalThis.safeJobCheck = { checks, checkJobPost };
