export default function App() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-6xl flex-col px-6 sm:px-12">
      <header className="border-b border-[#cbd8cc] py-7">
        <p className="text-2xl font-bold tracking-tight text-[#244c3e]">
          Rostaroo
          <span aria-hidden="true" className="text-[#537d64]">
            .
          </span>
        </p>
      </header>

      <main className="flex flex-1 flex-col justify-center py-16 sm:py-24">
        <div className="max-w-4xl rounded-[2rem] border border-[#d7e1d6] bg-[#eef3e9] px-6 py-12 sm:px-14 sm:py-16 lg:px-20">
          <p className="mb-6 inline-block rounded-full bg-[#dce8dc] px-4 py-2 text-sm font-semibold text-[#244c3e]">
            In development
          </p>
          <h1 className="max-w-[15ch] font-serif text-4xl leading-[1.08] tracking-tight text-[#1c3a31] sm:text-6xl lg:text-7xl">
            Staff rostering for Australian hospitality
          </h1>
          <p className="mt-6 max-w-[48ch] text-base leading-relaxed text-[#40564c] sm:text-lg">
            We’re building Rostaroo to help cafés and restaurants plan weekly
            rosters and give staff one place to check shifts and share
            availability.
          </p>
        </div>
      </main>

      <footer className="border-t border-[#cbd8cc] py-6 text-sm text-[#40564c]">
        Adelaide, South Australia
      </footer>
    </div>
  )
}
