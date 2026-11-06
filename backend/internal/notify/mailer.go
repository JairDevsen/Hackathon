// Package notify envia e-mails (2FA, convites, alertas). Driver "log" imprime no stdout (dev/testes).
package notify

import (
	"fmt"
	"log/slog"
	"mime"
	"net/smtp"
	"strings"
	"time"
)

type Mailer interface {
	Send(to, subject, body string) error
}

type LogMailer struct{ Sent chan string }

func (m *LogMailer) Send(to, subject, body string) error {
	slog.Info("email (driver log)", "to", to, "subject", subject, "body", body)
	if m.Sent != nil {
		select {
		case m.Sent <- to + "\n" + subject + "\n" + body:
		default:
		}
	}
	return nil
}

type SMTPMailer struct{ Host, Port, User, Pass, From string }

func (m *SMTPMailer) Send(to, subject, body string) error {
	var auth smtp.Auth
	if m.User != "" {
		auth = smtp.PlainAuth("", m.User, m.Pass, m.Host)
	}
	from := m.From
	if i := strings.Index(from, "<"); i >= 0 {
		from = strings.Trim(from[i:], "<>")
	}
	msg := fmt.Sprintf("From: %s\r\nTo: %s\r\nSubject: %s\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nDate: %s\r\n\r\n%s",
		m.From, to, mime.BEncoding.Encode("UTF-8", subject), time.Now().Format(time.RFC1123Z), body)
	return smtp.SendMail(m.Host+":"+m.Port, auth, from, []string{to}, []byte(msg))
}

func New(driver, host, port, user, pass, from string) Mailer {
	if driver == "smtp" {
		return &SMTPMailer{host, port, user, pass, from}
	}
	return &LogMailer{}
}
