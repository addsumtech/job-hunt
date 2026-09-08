-- The report's warning emoji is not covered by many text fonts. Keep its
-- meaning in PDF output without modifying the Markdown source or its facts.
function Str(element)
  if FORMAT:match('latex') then
    element.text = element.text:gsub('⚠️', '[!]'):gsub('⚠', '[!]')
  end
  return element
end
