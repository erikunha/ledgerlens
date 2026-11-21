/**
 * The PostCSS configuration of the public site.
 *
 * Tailwind compiles the utility classes and Autoprefixer adds the vendor prefixes the
 * browsers of the supported range need.
 */
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};

export default config;
