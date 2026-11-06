package cpf

import "testing"

func TestValid(t *testing.T) {
	cases := map[string]bool{"529.982.247-25": true, "52998224725": true, "111.111.111-11": false, "123": false, "529.982.247-24": false}
	for in, want := range cases {
		if got := Valid(in); got != want {
			t.Errorf("Valid(%q)=%v want %v", in, got, want)
		}
	}
	if Mask("52998224725") != "***.982.247-**" {
		t.Error("máscara")
	}
}
