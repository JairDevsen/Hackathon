package batches

import (
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"os"
	"strings"
	"time"
)

// ScanClamAV envia o arquivo ao clamd (INSTREAM). addr vazio = antivírus desligado (somente dev).
func ScanClamAV(addr, path string) error {
	if addr == "" {
		return nil
	}
	conn, err := net.DialTimeout("tcp", addr, 5*time.Second)
	if err != nil {
		return fmt.Errorf("antivírus indisponível: %w", err)
	}
	defer conn.Close()
	conn.SetDeadline(time.Now().Add(10 * time.Minute))
	if _, err := conn.Write([]byte("zINSTREAM\x00")); err != nil {
		return err
	}
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	buf := make([]byte, 64*1024)
	for {
		n, rerr := f.Read(buf)
		if n > 0 {
			hdr := make([]byte, 4)
			binary.BigEndian.PutUint32(hdr, uint32(n))
			if _, err := conn.Write(append(hdr, buf[:n]...)); err != nil {
				return err
			}
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			return rerr
		}
	}
	conn.Write([]byte{0, 0, 0, 0})
	resp, _ := io.ReadAll(conn)
	if !strings.Contains(string(resp), "OK") {
		return fmt.Errorf("arquivo rejeitado pelo antivírus: %s", strings.TrimSpace(string(resp)))
	}
	return nil
}
