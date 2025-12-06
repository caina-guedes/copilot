import fs from 'fs-extra'
import path from 'path'

const distDir = path.resolve('dist')
const foldersToMerge = ['content', 'background']
const filesToMove = ['content.js', 'background.js', 'icon.png', 'manifest.json', 'popup.html']

async function mergeDist() {
  try {
    for (const folder of foldersToMerge) {
      const folderPath = path.join(distDir, folder)
      for (const file of filesToMove) {
        const src = path.join(folderPath, file)
        const dest = path.join(distDir, file)

        if (await fs.pathExists(src)) {
          await fs.move(src, dest, { overwrite: true })
          console.log(`✅ Movido: ${file} de ${folder} para dist/`)
        }
      }
            // Move a pasta modularScrips (caso exista) pra raiz da dist
      const modularScriptsPath = path.join(folderPath, 'modularScrips');
      const modularScriptsDest = path.join(distDir, 'modularScrips');

      if (await fs.pathExists(modularScriptsPath)) {
        await fs.move(modularScriptsPath, modularScriptsDest, { overwrite: true });
        console.log(`📦 Pasta modularScrips movida de ${folder} para dist/`);
      }

      // Remove a pasta após mover os arquivos
      console.log(`🔍 Conteúdo de ${folderPath}:`, await fs.readdir(folderPath))
      await fs.remove(folderPath)
      console.log(`🧹 Pasta removida: ${folderPath}`)
    }

    console.log('🎉 Merge finalizado com sucesso!')
  } catch (error) {
    console.error('❌ Erro durante o merge:', error)
  }
}

mergeDist()
