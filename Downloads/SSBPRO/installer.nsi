!define APPNAME "LeanTraderBot Mini v4"
!define COMPANY "LeanTrader Technologies"
!define VERSION "4.0"
!define INSTALLDIR "$PROGRAMFILES\LeanTraderBotMiniV4"

OutFile "LeanTraderBot_Installer.exe"
InstallDir "${INSTALLDIR}"

RequestExecutionLevel admin
SetCompressor lzma

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install LeanTraderBot"
  SetOutPath "$INSTDIR"

  ; Main application EXE
  File "dist\LeanTraderBot_GUI.exe"

  ; Configuration template
  File "config.sample.json"

  ; Documentation
  File "README_INSTALL.md"

  ; Branding folder
  CreateDirectory "$INSTDIR\branding"
  File /r "branding\*.*"

  ; Desktop shortcut
  CreateShortCut "$DESKTOP\LeanTraderBot Mini v4.lnk" "$INSTDIR\LeanTraderBot_GUI.exe"

  ; Start menu folder and shortcut
  CreateDirectory "$SMPROGRAMS\LeanTraderBot Mini v4"
  CreateShortCut "$SMPROGRAMS\LeanTraderBot Mini v4\LeanTraderBot.lnk" "$INSTDIR\LeanTraderBot_GUI.exe"

  ; Uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\LeanTraderBot Mini v4.lnk"
  Delete "$SMPROGRAMS\LeanTraderBot Mini v4\LeanTraderBot.lnk"
  RMDir "$SMPROGRAMS\LeanTraderBot Mini v4"

  Delete "$INSTDIR\LeanTraderBot_GUI.exe"
  Delete "$INSTDIR\config.sample.json"
  Delete "$INSTDIR\README_INSTALL.md"
  RMDir /r "$INSTDIR\branding"

  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
