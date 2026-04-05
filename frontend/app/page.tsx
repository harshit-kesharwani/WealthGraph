import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6 py-16">
      <p className="text-sm font-medium uppercase tracking-widest text-mint-500">WealthGraph</p>
      <h1 className="mt-4 font-display text-4xl font-bold text-white md:text-5xl">
        Your money, your rules — clearer next steps
      </h1>
      <p className="mt-6 text-lg text-gray-400">
        Set goals and safety limits, see your portfolio in one place, and get plain-language
        suggestions you can approve or skip. Built for a smooth, guided experience.
      </p>
      <div className="mt-10 flex flex-wrap gap-4">
        <Link
          href="/login"
          className="rounded-lg bg-mint-500 px-6 py-3 font-medium text-ink-950 hover:bg-mint-400"
        >
          Log in
        </Link>
        <Link
          href="/signup"
          className="rounded-lg border border-gray-600 px-6 py-3 font-medium text-white hover:border-mint-500"
        >
          Sign up
        </Link>
      </div>
    </div>
  );
}
