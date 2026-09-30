import { SUPPORT_EMAIL } from "@/lib/copy";

/** The landing page's questions: the product guide's "Common questions", plus its WhatsApp costs. */
export const FAQ: { question: string; answer: string }[] = [
  {
    question: "Can Social Hood reply to my customers automatically?",
    answer:
      "Yes. With Auto mode (Pro), the AI replies by itself when it's confident, using your knowledge base. Anything it isn't sure about goes to \"Needs you\" for a person to answer. On Free, the AI suggests replies and you send them.",
  },
  {
    question: "Will the AI make things up?",
    answer:
      "The AI is instructed to answer only from your knowledge base and your conversation. When the answer isn't there, it doesn't guess: it hands the conversation to you and records the question as a knowledge gap.",
  },
  {
    question: "Does it work with a personal Instagram account?",
    answer:
      "No. Instagram only allows business tools on professional (Business or Creator) accounts. Switching is free in the Instagram app's settings.",
  },
  {
    question: "Can I connect more than one Instagram account?",
    answer: "Yes. Free includes 1 account per platform, and Pro includes 3.",
  },
  {
    question: "Why can't I message a customer who wrote to me days ago?",
    answer:
      "Instagram only allows businesses to message a customer within 24 hours of the customer's last message. Once they write again, you can reply. Social Hood shows when this window closes.",
  },
  {
    question: "Can my automation require people to follow me before sending the link?",
    answer:
      "No. Instagram's rules don't allow making a follow a condition. Social Hood can politely invite people to follow, and it always sends what they asked for.",
  },
  {
    question: "Does Social Hood post to my account without asking?",
    answer:
      "No. It only publishes posts you create and schedule. Ask Social Hood never publishes, sends or changes anything by itself.",
  },
  {
    question: "Which languages does the AI support?",
    answer: "English, Hindi and Hinglish.",
  },
  {
    question: "Is there a mobile app?",
    answer:
      "Social Hood works in any modern browser on phone and computer, and you can install it as an app from the browser to get push notifications. On iPhone, add it to your Home Screen first (iOS 16.4 or later).",
  },
  {
    question: "What happens when I run out of AI credits?",
    answer: "AI features pause until your credits reset or you upgrade. Everything else keeps working.",
  },
  {
    question: "Do the plans include WhatsApp's messaging fees?",
    answer:
      "No. Meta charges WhatsApp messaging fees directly to your business, based on Meta's own pricing.",
  },
  {
    question: "Can I cancel anytime?",
    answer: "Yes. Pro stays active until the end of the period you've paid for, then your workspace moves to Free.",
  },
  {
    question: "How do I contact support?",
    answer: `Email ${SUPPORT_EMAIL}.`,
  },
];
