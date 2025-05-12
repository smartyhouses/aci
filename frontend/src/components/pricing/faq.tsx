import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";

const faqs = [
  {
    value: "faq-1",
    question: "Can I upgrade my plan at any time?",
    answer: "xxx",
  },
  {
    value: "faq-2",
    question: "What happens if I exceed the API call limits?",
    answer: "xxx",
  },
  {
    value: "faq-3",
    question: "What is included in the Enterprise plan?",
    answer: "xxx",
  },
  {
    value: "faq-4",
    question: "What do you mean by authenticated users?",
    answer: "xxx",
  },
  { value: "faq-5", question: "Can I cancel my subscription?", answer: "xxx" },
  {
    value: "faq-6",
    question: "I need more enterprise features. Can you help?",
    answer: "xxx",
  },
  { value: "faq-7", question: "What is your refund policy?", answer: "xxx" },
];

export function FaqSection() {
  return (
    <div className="mx-auto max-w-2xl px-6 lg:px-8 mt-16">
      <h2 className="text-3xl font-bold text-center">
        Frequently Asked Questions
      </h2>
      <Accordion type="single" collapsible className="mt-6 space-y-2">
        {faqs.map(({ value, question, answer }) => (
          <AccordionItem key={value} value={value}>
            <AccordionTrigger>{question}</AccordionTrigger>
            <AccordionContent>{answer}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
