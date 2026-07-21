# NVDA için Terminal Erişimi (Terminal Access)

Terminal Erişimi; Windows Terminal, PowerShell, Komut İstemi (Command Prompt), WSL ve popüler üçüncü taraf emülatörler dahil olmak üzere 30'dan fazla Windows terminal uygulamasına klavye odaklı inceleme, gezinme, arama, yer imleri ve sesli ipuçları ekler. Terminal çıktılarında imleci hareket ettirmeden satır, kelime ve karakter bazında gezinmenizi sağlayarak, komut sonuçlarını bir belge okur gibi okumanıza olanak tanır.

Bu kılavuzu herhangi bir terminalin içindeyken **NVDA+Shift+F1** tuşlarına basarak dilediğiniz zaman açabilirsiniz.

## İçindekiler

1. [Başlangıç](#başlangıç)
2. [Komut Katmanı](#komut-katmanı)
3. [Arabellek Penceresi](#arabellek-penceresi)
4. [Tablo Modu](#tablo-modu)
5. [Yer İmleri](#yer-imleri)
6. [Hata ve Uyarı Tespiti](#hata-ve-uyarı-tespiti)
7. [Kısayol Çakışma Tespiti](#kısayol-çakışma-tespiti)
8. [Uygulama Profilleri](#uygulama-profilleri)
9. [Ayarlar](#ayarlar)
10. [Sorun Giderme](#sorun-giderme)

---

## Başlangıç

### İlk Adımlar

Desteklenen herhangi bir terminali açın. Terminal Erişimi bunu tanıdığında şunu duyacaksınız: "Terminal Erişimi desteği aktif. Yardım için NVDA+Shift+F1'e basın."

Terminal çıktısını iki şekilde okuyabilirsiniz:

- **Doğrudan kısayollar**: Geçerli satırı okumak için **NVDA+I** gibi NVDA değiştirici tuş kombinasyonları. Bunlar terminal içinde herhangi bir zamanda çalışır.
- **Komut katmanı**: Her komutun tek bir tuş basımı olduğu bir moda girmek için **NVDA+Kesme işareti (')** tuşuna basın. "Terminal komutları" ve yüksek perdeli bir ses duyacaksınız. Çıkmak için **Escape** tuşuna basın.

Komut katmanı, bir dizi komutu peş peşe kullanırken daha hızlıdır ve diğer eklentilerle çakışmayı önler. Her iki yöntem de aynı komutları çalıştırır ve NVDA'nın Girdi Hareketleri iletişim kutusundaki "Terminal Erişimi" altından her kısayolu yeniden atayabilirsiniz.

### Temel Okuma Komutları

Bu birkaç komut çoğu okuma işlemini kapsar. İlk sütun komut katmanı içindeki tuşu, ikinci sütun ise eşdeğer doğrudan kısayolu gösterir.

| Komut katmanı | Doğrudan kısayol | Eylem |
|---------------|----------------|--------|
| **I / O / U** | **NVDA+I / O / U** | Geçerli / sonraki / önceki satırı oku |
| **K / L / J** | **NVDA+K / L / J** | Geçerli / sonraki / önceki kelimeyi oku |
| **Virgül / Nokta / M** | **NVDA+virgül / nokta / M** | Geçerli / sonraki / önceki karakteri oku |
| **A** | **NVDA+A** | Sürekli okuma (tümünü oku) |
| **Noktalı virgül (;)** | **NVDA+noktalı virgül (;)** | Konumu duyur (satır, sütun) |
| **Escape** | | Komut katmanından çık |

*(İngilizce kılavuzun tamamı eklentinin özelliklerini daha ayrıntılı olarak açıklamaktadır. Gelişmiş özellikler için İngilizce kılavuza başvurabilirsiniz.)*

## Komut Katmanı

Komut katmanı, Terminal Erişimi komutlarını çok tuşlu NVDA değiştirici kombinasyonları yerine tek tuşla çalıştıran kalıcı bir giriş modudur. Bu, diğer NVDA eklentileriyle çakışmaları önler ve komutların yazılmasını hızlandırır.

### Giriş ve Çıkış

| Kısayol | Eylem |
|--------------------------------|--------------------------------------------------------------------------|
| **NVDA+Kesme işareti (')** | Komut katmanına gir. "Terminal komutları" ve yüksek perdeli bir ses duyarsınız. |
| **Escape** veya **NVDA+Kesme İşareti (')** | Komut katmanından çık. "Terminal komutlarından çık" ve alçak perdeli bir ses duyarsınız. |

Katman siz çıkana kadar aktif kalır. Her komut, komutları zincirleyebilmeniz için sizi katmanda tutar. Odak terminalden ayrıldığında katman kendi kendine kapanır.
