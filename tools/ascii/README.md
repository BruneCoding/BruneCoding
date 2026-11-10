# tools/ascii

Offline renderer for the [ascii-magic](https://www.ascii-magic.com) pieces used on the profile.

- `pieces/*.js`   the five pieces, copied from ascii-magic.com/ascii/pieces/
- `lib/kit.js`    a stand-in for ascii-magic's `lib/kit.js`, so they run without a network
- `render.mjs`    runs a piece in Node and dumps its frames as JSON
- `../build_ascii.py` turns those frames into GIFs / the moon SVG

To render with the *real* kit (identical noise and clouds to the live site), overwrite the stand-in:

    curl -o tools/ascii/lib/kit.js https://www.ascii-magic.com/ascii/lib/kit.js
    python tools/build_ascii.py all

(`lib/kit.js` sits next to `pieces/` on the site, which is why the pieces import `../lib/kit.js`.)
