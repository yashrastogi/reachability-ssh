package main

import (
	"bufio"
	"bytes"
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"golang.org/x/crypto/ssh"
)

func main() {
	reader := bufio.NewReader(os.Stdin)

	fmt.Print("Enter server IP: ")
	IP, _ := reader.ReadString('\n')
	IP = strings.Replace(IP, "\r\n", "", -1)

	fmt.Print("Enter server username: ")
	User, _ := reader.ReadString('\n')
	User = strings.Replace(User, "\r\n", "", -1)

	fmt.Printf("\nConnecting to %s (%s)...\n", IP, User)

	IP = IP + ":22"

	fmt.Print("Enter password: ")
	Pass, _ := reader.ReadString('\n')
	Pass = strings.Replace(Pass, "\r\n", "", -1)

	config := &ssh.ClientConfig{
		User: User,
		Auth: []ssh.AuthMethod{
			ssh.Password(Pass),
		},
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
	}
	Pass = "cleared password"

	conn, err := ssh.Dial("tcp", IP, config)
	if err != nil {
		panic(err)
	}

	fmt.Print("\nDrag IP targets file: ")
	fileIPPath, _ := reader.ReadString('\n')
	fileIPPath = strings.Replace(fileIPPath, "\r\n", "", -1)
	fmt.Println()

	fileIP, err := os.Open(fileIPPath)
	if err != nil {
		panic(err)
	}
	fileScanner := bufio.NewScanner(fileIP)
	fileScanner.Split(bufio.ScanLines)
	TTL := "15"

	fileName := filepath.Base(fileIPPath)
	fileNameArr := strings.Split(fileName, ".")
	csvFileName := strings.Join(fileNameArr[0:len(fileNameArr)-1], "") + ".csv"

	csvFile, err := os.Create(filepath.Join("./", "reports", csvFileName))
	if err != nil {
		panic(err)
	}
	defer csvFile.Close()
	writer := csv.NewWriter(csvFile)
	writer.Write([]string{"IP Address", "Ping Status", "Reachability Status", "Traceroute Output"})

	regex := regexp.MustCompile(fmt.Sprintf(`(?i)(unreachable|unable|timed out|%s  \* \* \*)`, TTL))
	for fileScanner.Scan() {
		reachStatus := "Reachable"
		pingStatus := "Success"
		IPcurr := fileScanner.Text()
		fmt.Printf("Pinging %s\t: ", IPcurr)
		session, err := conn.NewSession()
		var b bytes.Buffer
		session.Stdout = &b

		if err != nil {
			panic(err)
		}
		if err := session.Run(fmt.Sprintf("ping -c1 %s", IPcurr)); err != nil {
			fmt.Println("Not Reachable, starting traceroute...")
			pingStatus = "Failure"
		} else {
			fmt.Println("Reachable, starting traceroute...")
		}
		session.Close()
		b.Reset()
		session, err = conn.NewSession()
		session.Stdout = &b
		if err != nil {
			panic(err)
		}

		if err := session.Run(fmt.Sprintf("traceroute -n -m %s %s", TTL, IPcurr)); err != nil {
			fmt.Println(err)
		}
		traceOut := b.String()

		if regex.MatchString(traceOut) {
			reachStatus = "Not Reachable"
		}

		writer.Write([]string{IPcurr, pingStatus, reachStatus, traceOut})
	}
	writer.Flush()
	defer conn.Close()
	fmt.Println("\nPing/Traceroute completed.")
	time.Sleep(5 * time.Second)
}
