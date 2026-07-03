const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    
    const renderSvg = async (svgFile, width, height, outName) => {
        let svgContent = fs.readFileSync(svgFile, 'utf8');
        // ensure it scales to viewport
        svgContent = svgContent.replace(/width="\d+"/g, 'width="100%"').replace(/height="\d+"/g, 'height="100%"');
        const html = `<!DOCTYPE html><html><body style="margin:0;padding:0;">${svgContent}</body></html>`;
        
        await page.setViewport({ width, height });
        await page.setContent(html);
        await page.screenshot({ path: outName, omitBackground: true });
    };
    
    await renderSvg('cascade-logo-icon.svg', 512, 512, 'cascade-logo-icon-512.png');
    await renderSvg('cascade-logo-icon.svg', 32, 32, 'cascade-logo-favicon-32.png');
    await renderSvg('cascade-logo-full.svg', 1024, 1024, 'cascade-logo-full-1024.png');
    
    await browser.close();
    console.log("PNGs rendered.");
})();
